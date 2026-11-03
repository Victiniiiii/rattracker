"""Schema-driven settings dialog with profile management."""

from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .config import DEFAULT_PROFILE_NAME, POINT_KEYS, config_to_share_string
from .i18n import translate


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    group: str
    kind: str = "float"
    desc: str = ""
    minimum: float = 0
    maximum: float = 1000000
    step: float = 1
    decimals: int = 1


FIELDS = [
    Field("quadrantcross", "quadrantcross", "features", "bool", "quadrantcross_desc"),
    Field("platformcross", "platformcross", "features", "bool", "platformcross_desc"),
    Field("paraplatform_enabled", "paraplatform", "features", "bool", "paraplatform_desc"),
    Field("paraplatform_scale", "paraplatform_scale", "features", "int",
          "paraplatform_scale_desc", 1, 100, 1),
    Field("proximity", "proximity", "features", "bool", "proximity_desc"),
    Field("latency", "latency", "features", "bool", "latency_desc"),
    Field("tracemapcolor_enabled", "tracemapcolor", "features", "bool", "tracemapcolor_desc"),
    Field("tracemapcolor", "color", "features", "color"),
    Field("ratcolor_enabled", "ratcolor", "features", "bool", "ratcolor_desc"),
    Field("ratcolor", "color", "features", "color"),

    Field("mog2_history_s", "mog2_history_s", "detection", "float",
          "mog2_history_s_desc", 0.1, 3600, 0.1, 1),
    Field("mog2_threshold", "mog2_threshold", "detection", "float",
          "mog2_threshold_desc", 1, 255, 1, 1),
    Field("min_contour_area", "min_area", "detection", "float",
          "min_area_desc", 0, 100000000, 10, 1),
    Field("max_contour_area", "max_area", "detection", "float",
          "max_area_desc", 0, 100000000, 10, 1),
    Field("morph_open_k", "morph_open", "detection", "int",
          "morph_open_desc", 1, 999, 2),
    Field("morph_close_k", "morph_close", "detection", "int",
          "morph_close_desc", 1, 999, 2),
    Field("trail_s", "trail_s", "detection", "float",
          "trail_s_desc", 0.1, 600, 0.1, 1),
    Field("debug_frames", "debug_frames", "detection", "int",
          "debug_frames_desc", 0, 100000, 1),
    Field("mog2_learning_rate", "mog2_learning_rate", "detection", "float",
          "mog2_learning_rate_desc", -1, 1, 0.001, 3),
    Field("max_interp_gap", "max_interp_gap", "detection", "int",
          "max_interp_gap_desc", 0, 100000, 1),
    Field("heatmap_sigma", "heatmap_sigma", "detection", "float",
          "heatmap_sigma_desc", 0, 500, 0.5, 1),
    Field("mog2_detect_shadow", "detect_shadows", "detection", "bool", "detect_shadows_desc"),
    Field("autoconfig", "autoconfig", "detection", "bool", "autoconfig_desc"),
    Field("colorall", "colorall", "detection", "bool", "colorall_desc"),
]

for _key, _label in (
    ("pool_west", "pool_west"), ("pool_north", "pool_north"),
    ("pool_east", "pool_east"), ("pool_south", "pool_south"),
):
    FIELDS.append(Field(_key, _label, "pool", "point"))

for _key, _label in (
    ("platform_nw", "platform_nw"), ("platform_ne", "platform_ne"),
    ("platform_se", "platform_se"), ("platform_sw", "platform_sw"),
):
    FIELDS.append(Field(_key, _label, "platform", "point"))

GROUP_TITLES = {
    "features": "features",
    "detection": "detection",
    "pool": "pool_calib",
    "platform": "platform_calib",
}
GROUP_NOTES = {
    "features": "features_note",
    "pool": "pool_note",
    "platform": "platform_note",
}

POINT_RE = re.compile(r"^\s*-?\d+\s*,\s*-?\d+\s*$")


class SettingsDialog(QDialog):
    saved = Signal(dict)

    def __init__(self, store, lang: str = "en", parent=None):
        super().__init__(parent)
        self.store = store
        self.lang = lang
        self.widgets: dict[str, QWidget] = {}
        self.fields_by_key = {field.key: field for field in FIELDS}
        self.setWindowTitle(translate(lang, "settings"))
        self.setModal(True)
        self.resize(820, 840)

        outer = QVBoxLayout(self)
        outer.addLayout(self._build_profile_bar())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.form_host = QWidget()
        self.form_layout = QVBoxLayout(self.form_host)
        self.form_layout.setContentsMargins(4, 4, 4, 4)
        self.form_layout.setSpacing(10)
        self.scroll.setWidget(self.form_host)
        outer.addWidget(self.scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(translate(lang, "save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(translate(lang, "cancel"))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._build_form()
        self.populate(self.store.config())

    def _build_profile_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.addWidget(QLabel(translate(self.lang, "profile")))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(180)
        self.profile_combo.currentTextChanged.connect(self._switch_profile)
        bar.addWidget(self.profile_combo)

        def icon_button(path: str, tooltip: str) -> QPushButton:
            button = QPushButton()
            button.setIcon(_icon(path))
            button.setToolTip(tooltip)
            button.setFixedWidth(32)
            return button

        self.new_button = icon_button("plus.svg", translate(self.lang, "profile_new"))
        self.rename_button = icon_button("pencil.svg", translate(self.lang, "profile_rename"))
        self.delete_button = icon_button("trash.svg", translate(self.lang, "profile_delete"))
        self.share_button = icon_button("share.svg", translate(self.lang, "profile_share"))
        self.import_button = icon_button("import.svg", translate(self.lang, "profile_import"))
        self.new_button.clicked.connect(self._new_profile)
        self.rename_button.clicked.connect(self._rename_profile)
        self.delete_button.clicked.connect(self._delete_profile)
        self.share_button.clicked.connect(self._share_profile)
        self.import_button.clicked.connect(self._import_profile)
        for button in (self.new_button, self.rename_button, self.delete_button,
                       self.share_button, self.import_button):
            bar.addWidget(button)
        bar.addStretch(1)
        self._refresh_profiles()
        return bar

    def _refresh_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(sorted(self.store.profiles.keys()))
        self.profile_combo.setCurrentText(self.store.active)
        self.profile_combo.blockSignals(False)
        is_default = self.store.active == DEFAULT_PROFILE_NAME
        self.rename_button.setEnabled(not is_default)
        self.delete_button.setEnabled(not is_default)

    def _build_form(self):
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.widgets.clear()
        lang = self.lang
        for group in ("features", "detection", "pool", "platform"):
            box = QGroupBox(translate(lang, GROUP_TITLES[group]))
            box_layout = QVBoxLayout(box)
            note_key = GROUP_NOTES.get(group)
            if note_key:
                note = QLabel(translate(lang, note_key))
                note.setWordWrap(True)
                note.setStyleSheet("color:#9aa0a6; font-size:11px;")
                box_layout.addWidget(note)

            form = QFormLayout()
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            for field in (item for item in FIELDS if item.group == group):
                row = self._build_row(field)
                if isinstance(row, tuple):
                    form.addRow(row[0], row[1])
                else:
                    form.addRow(row)
            box_layout.addLayout(form)
            self.form_layout.addWidget(box)
        self.form_layout.addStretch(1)
        self._update_conditions()

    def _description(self, key: str) -> QLabel:
        label = QLabel(translate(self.lang, key))
        label.setWordWrap(True)
        label.setStyleSheet("color:#9aa0a6; font-size:11px;")
        return label

    def _labeled(self, field: Field, widget: QWidget):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(widget)
        if field.desc:
            layout.addWidget(self._description(field.desc))
        return QLabel(translate(self.lang, field.label)), container

    def _build_row(self, field: Field):
        if field.kind == "bool":
            checkbox = QCheckBox(translate(self.lang, field.label))
            self.widgets[field.key] = checkbox
            if field.key == "paraplatform_enabled":
                checkbox.toggled.connect(self._update_conditions)
            elif field.key == "tracemapcolor_enabled":
                checkbox.toggled.connect(self._update_conditions)
            elif field.key == "ratcolor_enabled":
                checkbox.toggled.connect(self._update_conditions)
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(checkbox)
            if field.desc:
                layout.addWidget(self._description(field.desc))
            return container

        if field.kind == "point":
            edit = QLineEdit()
            edit.setPlaceholderText("e.g. 320,240")
            self.widgets[field.key] = edit
            return QLabel(translate(self.lang, field.label)), edit

        if field.kind == "color":
            button = QPushButton()
            button.setFixedHeight(26)
            button.clicked.connect(lambda _=False, key=field.key: self._pick_color(key))
            self.widgets[field.key] = button
            return QLabel(translate(self.lang, field.label)), button

        if field.kind == "int":
            spin = QSpinBox()
            spin.setRange(int(field.minimum), int(field.maximum))
            spin.setSingleStep(int(field.step))
            spin.setKeyboardTracking(False)
            self.widgets[field.key] = spin
            return self._labeled(field, spin)

        spin = QDoubleSpinBox()
        spin.setRange(field.minimum, field.maximum)
        spin.setSingleStep(field.step)
        spin.setDecimals(field.decimals)
        spin.setKeyboardTracking(False)
        self.widgets[field.key] = spin
        return self._labeled(field, spin)

    def _pick_color(self, key: str):
        current = QColor(self._color_value(key))
        color = QColorDialog.getColor(current, self, translate(self.lang, "tracemapcolor"))
        if color.isValid():
            self.widgets[key].setText(color.name())
            self._update_color_button(key)

    def _color_value(self, key: str) -> str:
        button = self.widgets.get(key)
        text = button.text() if isinstance(button, QPushButton) else ""
        return text if text.startswith("#") else "#00ffff"

    def _update_color_button(self, key: str):
        button = self.widgets.get(key)
        if not isinstance(button, QPushButton):
            return
        value = button.text() or "#00ffff"
        button.setText(value)
        button.setStyleSheet(
            f"background:{value}; color:{_contrast(value)}; border:1px solid #555; padding:2px;"
        )

    def _update_conditions(self):
        pairs = [
            ("paraplatform_enabled", "paraplatform_scale"),
            ("tracemapcolor_enabled", "tracemapcolor"),
            ("ratcolor_enabled", "ratcolor"),
        ]
        for toggle_key, target_key in pairs:
            toggle = self.widgets.get(toggle_key)
            target = self.widgets.get(target_key)
            if toggle is not None and target is not None:
                target.setEnabled(bool(toggle.isChecked()))
        self._update_color_button("tracemapcolor")
        self._update_color_button("ratcolor")

    def populate(self, cfg: dict):
        for key, widget in self.widgets.items():
            value = cfg.get(key)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value if value is not None else 0))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value if value is not None else 0))
            elif isinstance(widget, QLineEdit):
                widget.setText("" if value is None else str(value))
            elif isinstance(widget, QPushButton):
                widget.setText(str(value or "#00ffff"))
        self._update_conditions()

    def read_config(self) -> dict:
        cfg = dict(self.store.config())
        for key, widget in self.widgets.items():
            if isinstance(widget, QCheckBox):
                cfg[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                cfg[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                cfg[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                cfg[key] = widget.text().strip()
            elif isinstance(widget, QPushButton):
                cfg[key] = widget.text()
        return cfg

    def _validate(self) -> bool:
        cfg = self.read_config()
        for key in POINT_KEYS:
            value = cfg.get(key) or ""
            if value and not POINT_RE.match(value):
                QMessageBox.warning(self, translate(self.lang, "settings"),
                                    f"{translate(self.lang, 'invalid_point')}\n\n{key}: {value}")
                return False
        for key in ("morph_open_k", "morph_close_k"):
            if int(cfg.get(key, 1)) % 2 == 0:
                QMessageBox.warning(self, translate(self.lang, "settings"),
                                    f"{translate(self.lang, 'odd_kernel')}\n\n{key}")
                return False
        return True

    def _save(self):
        if not self._validate():
            return
        cfg = self.read_config()
        self.store.set_config(cfg)
        self.saved.emit(cfg)
        self.accept()

    def _switch_profile(self, name: str):
        if not name or name == self.store.active:
            return
        self.store.set_config(self.read_config())
        cfg = self.store.switch(name)
        self.populate(cfg)
        self._refresh_profiles()

    def _new_profile(self):
        name, ok = QInputDialog.getText(
            self, translate(self.lang, "profile_new_title"),
            translate(self.lang, "profile") + ":", text="",
        )
        if ok and self.store.create(name, self.read_config()):
            self.populate(self.store.config())
            self._refresh_profiles()

    def _rename_profile(self):
        name, ok = QInputDialog.getText(
            self, translate(self.lang, "profile_rename_title"),
            translate(self.lang, "profile") + ":", text=self.store.active,
        )
        if ok and self.store.rename(name):
            self._refresh_profiles()

    def _delete_profile(self):
        if self.store.active == DEFAULT_PROFILE_NAME:
            return
        answer = QMessageBox.question(
            self, translate(self.lang, "profile_delete"),
            f"{translate(self.lang, 'profile_delete')}: {self.store.active}?",
        )
        if answer == QMessageBox.StandardButton.Yes and self.store.delete():
            self.populate(self.store.config())
            self._refresh_profiles()

    def _text_dialog(self, title: str, text: str, read_only: bool, copy: bool = False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(640, 320)
        layout = QVBoxLayout(dialog)
        editor = QPlainTextEdit()
        editor.setPlainText(text)
        editor.setReadOnly(read_only)
        layout.addWidget(editor, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        if copy:
            copy_button = QPushButton(translate(self.lang, "copy"))
            copy_button.clicked.connect(lambda: editor.selectAll() or editor.copy())
            row.addWidget(copy_button)
        close_button = QPushButton(translate(self.lang, "close"))
        close_button.clicked.connect(dialog.accept)
        row.addWidget(close_button)
        layout.addLayout(row)
        dialog.exec()
        return editor.toPlainText()

    def _share_profile(self):
        text = config_to_share_string(self.read_config(), self.store.active)
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self._text_dialog(translate(self.lang, "profile_share_title"), text, True, True)

    def _import_profile(self):
        text = self._text_dialog(translate(self.lang, "profile_import_title"),
                                 "", False)
        if text.strip():
            self.store.import_config(text)
            self.populate(self.store.config())
            self._refresh_profiles()


def _icon(name: str):
    from PySide6.QtGui import QIcon

    from .resources import asset_path

    return QIcon(str(asset_path(name)))


def _contrast(hex_value: str) -> str:
    clean = hex_value.lstrip("#")
    try:
        value = int(clean, 16)
    except ValueError:
        return "#ffffff"
    r, g, b = (value >> 16) & 255, (value >> 8) & 255, value & 255
    return "#000000" if (r * 299 + g * 587 + b * 114) / 1000 > 140 else "#ffffff"
