from __future__ import annotations

import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QSize, Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QProgressBar, QSizePolicy, QVBoxLayout, QWidget,
)

from .cleaner import CleanOptions, clean_pdf


def _clean_one(task: tuple[str, str]) -> dict:
    source, output = task
    return clean_pdf(Path(source), Path(output), options=CleanOptions()).__dict__


class BatchWorker(QObject):
    progress = Signal(int, int, dict)
    completed = Signal(list)
    failed = Signal(str)

    def __init__(self, selections: list[str], replace_originals: bool, output_dir: str):
        super().__init__()
        self.selections = selections
        self.replace_originals = replace_originals
        self.output_dir = Path(output_dir)

    def run(self) -> None:
        try:
            files: list[tuple[Path, Path]] = []
            seen: set[Path] = set()
            for selection in map(Path, self.selections):
                if selection.is_dir():
                    for candidate in sorted(selection.rglob("*.pdf")):
                        resolved = candidate.resolve()
                        if not self.replace_originals and resolved.is_relative_to(self.output_dir.resolve()):
                            continue
                        if resolved not in seen:
                            files.append((resolved, selection.resolve()))
                            seen.add(resolved)
                elif selection.is_file() and selection.suffix.casefold() == ".pdf":
                    resolved = selection.resolve()
                    if resolved not in seen:
                        files.append((resolved, resolved.parent))
                        seen.add(resolved)
            if not files:
                self.completed.emit([])
                return

            tasks = []
            multiple_roots = len({root for _, root in files}) > 1
            for source, root in files:
                relative = source.relative_to(root)
                if multiple_roots:
                    relative = Path(root.name) / relative
                destination = source if self.replace_originals else self.output_dir / relative
                tasks.append((str(source), str(destination)))

            results = []
            with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
                futures = {pool.submit(_clean_one, task): task for task in tasks}
                for index, future in enumerate(as_completed(futures), 1):
                    source, output = futures[future]
                    try:
                        row = future.result()
                    except Exception as exc:
                        row = {"source": source, "output": output, "status": "error",
                               "error": f"{type(exc).__name__}: {exc}", "removed_pages": [],
                               "removed_regions": [], "removed_branding": []}
                    results.append(row)
                    self.progress.emit(index, len(tasks), row)
            self.completed.emit(results)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class DropZone(QFrame):
    paths_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.symbol = QLabel("↓")
        self.symbol.setObjectName("dropSymbol")
        self.symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heading = QLabel("Arrastra aquí tus PDFs o carpetas")
        self.heading.setObjectName("dropHeading")
        self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subheading = QLabel("Los subdirectorios también se incluirán")
        self.subheading.setObjectName("muted")
        self.subheading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.symbol)
        layout.addWidget(self.heading)
        layout.addWidget(self.subheading)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.paths_dropped.emit([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Nacho", "WuolahWoutAds")
        self.theme = self.settings.value("theme", "light")
        self.worker_thread: QThread | None = None
        self.worker: BatchWorker | None = None
        self._status_widgets: dict[str, QLabel] = {}
        self.setWindowTitle("Wuolah Wout Ads")
        self.setMinimumSize(760, 690)
        self.resize(880, 790)
        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(34, 26, 34, 28)
        page.setSpacing(18)

        header = QHBoxLayout()
        brand = QHBoxLayout()
        mark = QLabel("W")
        mark.setObjectName("brandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(42, 42)
        brand.addWidget(mark)
        title_box = QVBoxLayout()
        title = QLabel("Wuolah Wout Ads")
        title.setObjectName("appTitle")
        tagline = QLabel("Limpia tus apuntes. Todo se queda en tu equipo.")
        tagline.setObjectName("muted")
        title_box.addWidget(title)
        title_box.addWidget(tagline)
        brand.addLayout(title_box)
        header.addLayout(brand)
        header.addStretch()
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setFixedSize(42, 42)
        self.theme_button.clicked.connect(self._toggle_theme)
        header.addWidget(self.theme_button)
        page.addLayout(header)

        intro = QVBoxLayout()
        intro.setSpacing(5)
        headline = QLabel("Quita Wuolah de tus PDFs")
        headline.setObjectName("headline")
        description = QLabel("Añade archivos sueltos o una carpeta completa. Puedes seguir trabajando sin conexión.")
        description.setObjectName("muted")
        description.setWordWrap(True)
        intro.addWidget(headline)
        intro.addWidget(description)
        page.addLayout(intro)

        self.drop_zone = DropZone()
        self.drop_zone.paths_dropped.connect(self.add_paths)
        page.addWidget(self.drop_zone)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.files_button = QPushButton("＋   Añadir PDFs")
        self.files_button.setObjectName("secondaryButton")
        self.files_button.clicked.connect(self.pick_files)
        self.folder_button = QPushButton("▱   Añadir carpeta")
        self.folder_button.setObjectName("secondaryButton")
        self.folder_button.clicked.connect(self.pick_folder)
        buttons.addWidget(self.files_button)
        buttons.addWidget(self.folder_button)
        buttons.addStretch()
        self.clear_button = QPushButton("Vaciar lista")
        self.clear_button.setObjectName("textButton")
        self.clear_button.clicked.connect(self.clear_list)
        self.remove_button = QPushButton("Quitar seleccionado")
        self.remove_button.setObjectName("textButton")
        self.remove_button.clicked.connect(self.remove_selected)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.clear_button)
        page.addLayout(buttons)

        queue_header = QHBoxLayout()
        queue_title = QLabel("Tu lote")
        queue_title.setObjectName("sectionTitle")
        self.count_label = QLabel("0 elementos")
        self.count_label.setObjectName("muted")
        queue_header.addWidget(queue_title)
        queue_header.addStretch()
        queue_header.addWidget(self.count_label)
        page.addLayout(queue_header)

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setAlternatingRowColors(False)
        self.file_list.setMinimumHeight(120)
        self.file_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        empty = QListWidgetItem()
        empty.setFlags(Qt.ItemFlag.NoItemFlags)
        empty.setSizeHint(self._empty_row_size())
        self.file_list.addItem(empty)
        self.file_list.setItemWidget(empty, self._empty_row())
        page.addWidget(self.file_list, 1)

        options = QFrame()
        options.setObjectName("optionsCard")
        option_layout = QVBoxLayout(options)
        option_layout.setContentsMargins(16, 14, 16, 14)
        option_layout.setSpacing(8)
        self.replace_checkbox = QCheckBox("Reemplazar los originales")
        self.replace_checkbox.setChecked(True)
        self.replace_checkbox.stateChanged.connect(self._update_output_visibility)
        option_layout.addWidget(self.replace_checkbox)
        safe_note = QLabel("Cada archivo se guarda de forma segura: si falla la limpieza, el original se conserva.")
        safe_note.setObjectName("muted")
        safe_note.setWordWrap(True)
        option_layout.addWidget(safe_note)
        self.output_button = QPushButton("Elegir carpeta de destino…")
        self.output_button.setObjectName("textButton")
        self.output_button.clicked.connect(self.choose_output)
        self.output_label = QLabel(str(Path.home() / "Documents" / "Wuolah limpio"))
        self.output_label.setObjectName("muted")
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_label, 1)
        output_row.addWidget(self.output_button)
        option_layout.addLayout(output_row)
        page.addWidget(options)

        footer = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.status_label = QLabel("Listo para limpiar")
        self.status_label.setObjectName("muted")
        status_box = QVBoxLayout()
        status_box.addWidget(self.status_label)
        status_box.addWidget(self.progress)
        footer.addLayout(status_box, 1)
        self.clean_button = QPushButton("Limpiar PDFs   →")
        self.clean_button.setObjectName("primaryButton")
        self.clean_button.setMinimumHeight(48)
        self.clean_button.clicked.connect(self.start_cleaning)
        footer.addWidget(self.clean_button)
        page.addLayout(footer)
        self._update_output_visibility()
        self._update_theme_button()

    def _apply_theme(self) -> None:
        dark = self.theme == "dark"
        colors = {
            "bg": "#111318" if dark else "#f5f6f8",
            "surface": "#191c23" if dark else "#ffffff",
            "surface2": "#20242d" if dark else "#eef0f4",
            "text": "#f1f3f7" if dark else "#1b1e26",
            "muted": "#a0a6b4" if dark else "#707787",
            "line": "#2b303b" if dark else "#e0e3e9",
            "accent": "#7258e8",
            "accent_hover": "#6046d7",
        }
        self.setStyleSheet(f"""
            QWidget#root {{ background: {colors['bg']}; color: {colors['text']}; font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 14px; }}
            QLabel {{ color: {colors['text']}; }}
            QLabel#muted {{ color: {colors['muted']}; font-size: 12px; }}
            QLabel#brandMark {{ background: {colors['accent']}; color: white; border-radius: 13px; font-size: 20px; font-weight: 800; }}
            QLabel#appTitle {{ font-size: 15px; font-weight: 700; }}
            QLabel#headline {{ font-size: 25px; font-weight: 750; letter-spacing: -0.5px; }}
            QLabel#sectionTitle {{ font-size: 14px; font-weight: 700; }}
            QFrame#dropZone {{ background: {colors['surface']}; border: 1px dashed {colors['line']}; border-radius: 18px; min-height: 150px; }}
            QFrame#dropZone:hover {{ border-color: {colors['accent']}; background: {colors['surface2']}; }}
            QLabel#dropSymbol {{ color: {colors['accent']}; font-size: 26px; font-weight: 500; }}
            QLabel#dropHeading {{ font-size: 15px; font-weight: 650; }}
            QListWidget#fileList {{ background: {colors['surface']}; border: 1px solid {colors['line']}; border-radius: 14px; padding: 7px; outline: none; }}
            QFrame#fileRow {{ background: transparent; border-radius: 9px; }}
            QFrame#fileRow:hover {{ background: {colors['surface2']}; }}
            QLabel#fileBadge {{ background: {colors['surface2']}; color: {colors['accent']}; border-radius: 8px; padding: 8px; font-size: 10px; font-weight: 800; }}
            QLabel#fileName {{ font-size: 13px; font-weight: 650; }}
            QLabel#filePath {{ color: {colors['muted']}; font-size: 11px; }}
            QLabel#statusChip {{ background: {colors['surface2']}; color: {colors['muted']}; border-radius: 8px; padding: 5px 9px; font-size: 11px; }}
            QLabel#emptyTitle {{ color: {colors['text']}; font-weight: 600; }}
            QPushButton#rowRemoveButton {{ color: {colors['muted']}; background: transparent; padding: 3px 8px; font-size: 18px; }}
            QPushButton#rowRemoveButton:hover {{ color: #e05d6f; background: {colors['surface2']}; }}
            QFrame#optionsCard {{ background: {colors['surface']}; border: 1px solid {colors['line']}; border-radius: 13px; }}
            QCheckBox {{ color: {colors['text']}; font-weight: 650; spacing: 9px; }}
            QCheckBox::indicator {{ width: 17px; height: 17px; }}
            QPushButton {{ border: 0; border-radius: 10px; padding: 10px 15px; font-weight: 600; }}
            QPushButton#primaryButton {{ background: {colors['accent']}; color: white; padding: 13px 21px; }}
            QPushButton#primaryButton:hover {{ background: {colors['accent_hover']}; }}
            QPushButton#primaryButton:disabled {{ background: {colors['line']}; color: {colors['muted']}; }}
            QPushButton#secondaryButton, QPushButton#themeButton {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['line']}; }}
            QPushButton#secondaryButton:hover, QPushButton#themeButton:hover {{ background: {colors['surface2']}; }}
            QPushButton#textButton {{ color: {colors['muted']}; background: transparent; padding: 7px; }}
            QPushButton#textButton:hover {{ color: {colors['accent']}; }}
            QProgressBar#progress {{ background: {colors['line']}; border: 0; border-radius: 4px; }}
            QProgressBar#progress::chunk {{ background: {colors['accent']}; border-radius: 4px; }}
        """)

    def _update_theme_button(self) -> None:
        self.theme_button.setText("☾" if self.theme == "light" else "☀")
        self.theme_button.setToolTip("Cambiar al tema oscuro" if self.theme == "light" else "Cambiar al tema claro")

    def _toggle_theme(self) -> None:
        self.theme = "dark" if self.theme == "light" else "light"
        self.settings.setValue("theme", self.theme)
        self._apply_theme()
        self._update_theme_button()

    def _update_output_visibility(self) -> None:
        visible = not self.replace_checkbox.isChecked()
        self.output_button.setVisible(visible)
        self.output_label.setVisible(visible)

    def add_paths(self, paths: list[str]) -> None:
        if self.worker_thread is not None:
            return
        existing = {self.file_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.file_list.count())}
        if self.file_list.count() == 1 and self.file_list.item(0).flags() == Qt.ItemFlag.NoItemFlags:
            self.file_list.clear()
        for raw in paths:
            path = Path(raw).expanduser()
            if not path.exists() or (not path.is_dir() and path.suffix.casefold() != ".pdf"):
                continue
            normalized = str(path.resolve())
            if normalized in existing:
                continue
            item = QListWidgetItem()
            item.setToolTip(normalized)
            item.setData(Qt.ItemDataRole.UserRole, normalized)
            self.file_list.addItem(item)
            row = self._path_row(path, normalized)
            self.file_list.setItemWidget(item, row)
            item.setSizeHint(row.sizeHint())
            existing.add(normalized)
        if self.file_list.count() == 0:
            empty = QListWidgetItem()
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setSizeHint(self._empty_row_size())
            self.file_list.addItem(empty)
            self.file_list.setItemWidget(empty, self._empty_row())
        self._refresh_count()

    def _empty_row_size(self):
        return QSize(300, max(92, self.file_list.viewport().height() - 14))

    def _empty_row(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(5)
        title = QLabel("La lista está vacía")
        title.setObjectName("emptyTitle")
        detail = QLabel("Arrastra PDFs aquí o selecciónalos arriba")
        detail.setObjectName("muted")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detail, alignment=Qt.AlignmentFlag.AlignCenter)
        return box

    def _path_row(self, path: Path, normalized: str) -> QWidget:
        row = QFrame()
        row.setObjectName("fileRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 7, 6, 7)
        layout.setSpacing(12)
        badge = QLabel("PDF" if path.is_file() else "DIR")
        badge.setObjectName("fileBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedWidth(42)
        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        name = QLabel(path.name)
        name.setObjectName("fileName")
        subpath = QLabel(normalized)
        subpath.setObjectName("filePath")
        subpath.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_box.addWidget(name)
        text_box.addWidget(subpath)
        text_box.setStretch(1, 1)
        status = QLabel("En cola")
        status.setObjectName("statusChip")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setMinimumWidth(78)
        self._status_widgets[normalized] = status
        remove = QPushButton("×")
        remove.setObjectName("rowRemoveButton")
        remove.setFixedSize(30, 30)
        remove.setToolTip("Quitar de la lista")
        remove.clicked.connect(lambda: self._remove_path(normalized))
        layout.addWidget(badge)
        layout.addLayout(text_box, 1)
        layout.addWidget(status)
        layout.addWidget(remove)
        return row

    def _remove_path(self, normalized: str) -> None:
        if self.worker_thread is not None:
            return
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == normalized:
                self.file_list.takeItem(index)
                break
        self._status_widgets.pop(normalized, None)
        self._refresh_count()

    def _set_item_status(self, normalized: str, label: str) -> None:
        status = self._status_widgets.get(normalized)
        if status:
            status.setText(label)

    def _refresh_count(self) -> None:
        count = sum(1 for i in range(self.file_list.count())
                    if self.file_list.item(i).data(Qt.ItemDataRole.UserRole))
        if count == 0 and self.file_list.count() == 0:
            empty = QListWidgetItem()
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setSizeHint(self._empty_row_size())
            self.file_list.addItem(empty)
            self.file_list.setItemWidget(empty, self._empty_row())
        self.count_label.setText(f"{count} elemento" if count == 1 else f"{count} elementos")
        self.clean_button.setEnabled(count > 0 and self.worker_thread is None)
        self.remove_button.setEnabled(count > 0 and self.worker_thread is None)
        self.clear_button.setEnabled(count > 0 and self.worker_thread is None)

    def pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Añadir PDFs", str(Path.home()), "PDFs (*.pdf)")
        self.add_paths(files)

    def pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Añadir carpeta de PDFs", str(Path.home()))
        if folder:
            self.add_paths([folder])

    def choose_output(self) -> None:
        current = self.output_label.text()
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de destino", current)
        if folder:
            self.output_label.setText(folder)

    def clear_list(self) -> None:
        if self.worker_thread is None:
            self.file_list.clear()
            self._status_widgets.clear()
            self._refresh_count()

    def remove_selected(self) -> None:
        if self.worker_thread is None:
            for item in self.file_list.selectedItems():
                self._status_widgets.pop(item.data(Qt.ItemDataRole.UserRole), None)
                self.file_list.takeItem(self.file_list.row(item))
            self._refresh_count()

    def start_cleaning(self) -> None:
        selections = [self.file_list.item(i).data(Qt.ItemDataRole.UserRole)
                      for i in range(self.file_list.count())
                      if self.file_list.item(i).data(Qt.ItemDataRole.UserRole)]
        if not selections:
            return
        if not self.replace_checkbox.isChecked():
            output = Path(self.output_label.text()).expanduser()
            same_file_parent = any(Path(path).is_file() and output.resolve() == Path(path).resolve().parent
                                   for path in selections)
            nested_in_input = any(Path(path).is_dir() and output.resolve().is_relative_to(Path(path).resolve())
                                  for path in selections)
            if same_file_parent or nested_in_input:
                QMessageBox.warning(self, "Carpeta de destino", "Elige una carpeta de destino fuera de la ubicación de origen.")
                return
        mode = "reemplazar los originales" if self.replace_checkbox.isChecked() else f"guardar copias en {self.output_label.text()}"
        answer = QMessageBox.question(self, "Empezar limpieza", f"Se procesarán los PDFs de la selección y se van a {mode}.\n\nLos archivos que no parezcan de Wuolah se omitirán. ¿Continuar?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Yes)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.clean_button.setEnabled(False)
        self.files_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.replace_checkbox.setEnabled(False)
        self.output_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status_label.setText("Preparando lote…")
        self.worker_thread = QThread(self)
        self.worker = BatchWorker(selections, self.replace_checkbox.isChecked(), self.output_label.text())
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.completed.connect(self._on_completed)
        self.worker.failed.connect(self._on_failed)
        self.worker.completed.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._on_thread_finished)
        self.worker_thread.start()

    def _on_progress(self, done: int, total: int, row: dict) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        name = Path(row["source"]).name
        self.status_label.setText(f"{done} de {total} · {name}: {self._status_text(row)}")
        source = Path(row["source"]).resolve()
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            value = item.data(Qt.ItemDataRole.UserRole)
            if not value:
                continue
            selected = Path(value).resolve()
            if source == selected:
                self._set_item_status(value, self._status_text(row).capitalize())
            elif selected.is_dir() and source.is_relative_to(selected):
                self._set_item_status(value, "Procesando")

    @staticmethod
    def _status_text(row: dict) -> str:
        return {"cleaned": "limpio", "unchanged": "sin cambios", "skipped": "omitido", "error": "error"}.get(row.get("status"), row.get("status", ""))

    def _on_completed(self, rows: list) -> None:
        cleaned = sum(row.get("status") == "cleaned" for row in rows)
        unchanged = sum(row.get("status") == "unchanged" for row in rows)
        skipped = sum(row.get("status") == "skipped" for row in rows)
        errors = sum(row.get("status") == "error" for row in rows)
        removed = sum(len(row.get("removed_pages", [])) for row in rows)
        removed += sum(len(row.get("removed_regions", [])) + len(row.get("removed_branding", [])) for row in rows)
        self.progress.setRange(0, max(1, len(rows)))
        self.progress.setValue(len(rows))
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            value = item.data(Qt.ItemDataRole.UserRole)
            if not value:
                continue
            selected = Path(value).resolve()
            matching = [row for row in rows if Path(row.get("source", "")).resolve() == selected
                        or (selected.is_dir() and Path(row.get("source", "")).resolve().is_relative_to(selected))]
            if selected.is_file() and matching:
                self._set_item_status(value, self._status_text(matching[0]).capitalize())
            elif selected.is_dir() and matching:
                clean_count = sum(row.get("status") == "cleaned" for row in matching)
                skip_count = sum(row.get("status") in {"skipped", "unchanged"} for row in matching)
                error_count = sum(row.get("status") == "error" for row in matching)
                self._set_item_status(value, f"{clean_count} limpios · {skip_count} sin cambios" + (f" · {error_count} errores" if error_count else ""))
            elif selected.is_dir():
                self._set_item_status(value, "Sin PDFs")
        if not rows:
            self.status_label.setText("No se encontraron PDFs en la selección")
        else:
            self.status_label.setText(f"Terminado · {cleaned} limpios · {unchanged} sin cambios · {skipped} omitidos · {errors} errores")
            QMessageBox.information(self, "Limpieza terminada",
                f"PDFs procesados: {len(rows)}\nLimpios: {cleaned}\nSin cambios: {unchanged}\nOmitidos: {skipped}\nErrores: {errors}\nMarcas y anuncios detectados: {removed}\n\nSolo se eliminan patrones que el detector puede reconocer.")

    def _on_failed(self, message: str) -> None:
        self.status_label.setText("No se pudo completar el lote")
        QMessageBox.critical(self, "Error al limpiar", message)

    def _on_thread_finished(self) -> None:
        self.worker_thread.deleteLater()
        self.worker_thread = None
        self.worker = None
        self.files_button.setEnabled(True)
        self.folder_button.setEnabled(True)
        self.replace_checkbox.setEnabled(True)
        self.output_button.setEnabled(True)
        self.progress.setRange(0, 1)
        self._refresh_count()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if (self.file_list.count() == 1
                and not self.file_list.item(0).data(Qt.ItemDataRole.UserRole)):
            self.file_list.item(0).setSizeHint(self._empty_row_size())

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()


def main() -> None:
    multiprocessing.freeze_support()
    app = QApplication([])
    app.setApplicationName("Wuolah Wout Ads")
    app.setOrganizationName("Nacho")
    app.setFont(QFont("Inter", 10))
    window = MainWindow()
    window.show()
    app.exec()
