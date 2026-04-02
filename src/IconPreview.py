from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import Icons
import UiExport
from Utils import get_main_window


APP_ICON_ASSETS = (
    ('Primary SVG', Icons.APP_ICON_FILE),
)


class IconPreviewDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mw = parent or get_main_window()

        self.setWindowTitle('Icon Preview')
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.setModal(True)
        self.resize(980, 780)
        self.setMinimumSize(860, 680)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)

        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(
            """
            QDialog {
                background: #edf3f8;
            }
            QFrame#previewHero {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #ffffff,
                    stop: 1 #eef5fb
                );
                border: 1px solid #d6e1ec;
                border-radius: 18px;
            }
            QFrame#previewSection,
            QFrame#previewRow {
                background: #ffffff;
                border: 1px solid #d6e1ec;
                border-radius: 16px;
            }
            QLabel#previewEyebrow {
                color: #687d91;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            QLabel#previewTitle {
                color: #172d43;
                font-size: 30px;
                font-weight: 700;
            }
            QLabel#previewSubtitle,
            QLabel#previewSectionBody,
            QLabel#previewMeta {
                color: #536679;
                font-size: 13px;
                line-height: 1.45em;
            }
            QLabel#previewBadge {
                background: #ffffff;
                border: 1px solid #d6e1ec;
                border-radius: 999px;
                color: #264562;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
            }
            QLabel#previewSectionTitle {
                color: #1b3047;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#previewRowTitle {
                color: #1f3348;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#previewRowPath {
                color: #6a7d90;
                font-size: 12px;
                font-family: "SF Mono", "Menlo", "Monaco", monospace;
            }
            QFrame#swatchCard,
            QFrame#assetCard {
                background: #f8fbfd;
                border: 1px solid #d9e3ed;
                border-radius: 12px;
            }
            QLabel#swatchSize,
            QLabel#assetLabel {
                color: #5c7185;
                font-size: 11px;
                font-weight: 700;
            }
            QDialogButtonBox QPushButton {
                background: #ffffff;
                border: 1px solid #c7d5e3;
                border-radius: 10px;
                color: #1d3249;
                font-weight: 600;
                min-width: 96px;
                padding: 8px 14px;
            }
            QDialogButtonBox QPushButton:hover {
                background: #f4f8fb;
                border-color: #9db7d4;
            }
            """
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._build_header())

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(self._build_app_assets_section())
        content_layout.addWidget(
            self._build_icon_section(
                title='Custom Domain Icons',
                description=(
                    'These are the icons we should keep iterating. '
                    'They use the Lucide stroke language but cover PyAero-specific concepts.'
                ),
                icon_names=Icons.names_for_family('custom'),
            )
        )
        content_layout.addWidget(
            self._build_icon_section(
                title='Lucide System Icons',
                description=(
                    'These are the semantic action icons wired through the icon registry. '
                    'Use them as the visual baseline when refining custom SVGs.'
                ),
                icon_names=Icons.names_for_family('lucide'),
            )
        )
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        UiExport.install_dialog_export_button(
            buttons,
            mainwindow=self.mw,
            widget=self,
            default_name='icon_preview_dialog.png',
            dialog_title='Export Icon Preview Dialog As',
            success_label='Icon preview dialog',
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _build_header(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName('previewHero')

        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(84, 84)
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        if self.windowIcon().isNull():
            pixmap = Icons.app_icon().pixmap(72, 72)
        else:
            pixmap = self.windowIcon().pixmap(72, 72)
        if not pixmap.isNull():
            icon_label.setPixmap(
                pixmap.scaled(
                    72,
                    72,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        layout.addWidget(icon_label, 0, QtCore.Qt.AlignTop)

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(8)

        eyebrow = QtWidgets.QLabel('Design Tooling')
        eyebrow.setObjectName('previewEyebrow')
        text_layout.addWidget(eyebrow)

        title = QtWidgets.QLabel('Icon Preview')
        title.setObjectName('previewTitle')
        text_layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            'Inspect every semantic icon at the sizes PyAero actually uses, '
            'and compare the custom domain icons against the Lucide baseline.'
        )
        subtitle.setObjectName('previewSubtitle')
        subtitle.setWordWrap(True)
        text_layout.addWidget(subtitle)

        badge_row = QtWidgets.QHBoxLayout()
        badge_row.setSpacing(8)
        for text in (
            f'{len(Icons.names_for_family("custom"))} custom icons',
            f'{len(Icons.names_for_family("lucide"))} Lucide icons',
            'Target sizes 16 / 20 / 24 / 32',
        ):
            badge = QtWidgets.QLabel(text)
            badge.setObjectName('previewBadge')
            badge_row.addWidget(badge)
        badge_row.addStretch(1)
        text_layout.addLayout(badge_row)

        layout.addLayout(text_layout, 1)
        return frame

    def _build_app_assets_section(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName('previewSection')

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QtWidgets.QLabel('App Icon Assets')
        title.setObjectName('previewSectionTitle')
        layout.addWidget(title)

        body = QtWidgets.QLabel(
            'This SVG is the canonical application icon source. '
            'It is rendered directly in the UI instead of relying on hard-coded PNG-only paths.'
        )
        body.setObjectName('previewSectionBody')
        body.setWordWrap(True)
        layout.addWidget(body)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        for label, relative_path in APP_ICON_ASSETS:
            row.addWidget(self._build_asset_card(label, relative_path))
        row.addStretch(1)
        layout.addLayout(row)
        return frame

    def _build_asset_card(self, label, relative_path):
        card = QtWidgets.QFrame()
        card.setObjectName('assetCard')
        card.setFixedWidth(170)

        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        asset_label = QtWidgets.QLabel(label)
        asset_label.setObjectName('assetLabel')
        layout.addWidget(asset_label)

        relative = QtWidgets.QLabel(relative_path)
        relative.setObjectName('previewMeta')
        relative.setWordWrap(True)
        layout.addWidget(relative)

        preview = QtWidgets.QLabel()
        preview.setAlignment(QtCore.Qt.AlignCenter)
        preview.setMinimumHeight(92)
        pixmap = QtGui.QIcon(str(Icons.ICON_ROOT / relative_path)).pixmap(72, 72)
        if not pixmap.isNull():
            preview.setPixmap(
                pixmap.scaled(
                    72,
                    72,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        layout.addWidget(preview, 1)

        return card

    def _build_icon_section(self, title, description, icon_names):
        frame = QtWidgets.QFrame()
        frame.setObjectName('previewSection')

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        heading = QtWidgets.QLabel(title)
        heading.setObjectName('previewSectionTitle')
        layout.addWidget(heading)

        body = QtWidgets.QLabel(description)
        body.setObjectName('previewSectionBody')
        body.setWordWrap(True)
        layout.addWidget(body)

        for icon_name in icon_names:
            layout.addWidget(self._build_icon_row(icon_name))

        return frame

    def _build_icon_row(self, icon_name):
        frame = QtWidgets.QFrame()
        frame.setObjectName('previewRow')

        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        meta_layout = QtWidgets.QVBoxLayout()
        meta_layout.setSpacing(4)
        meta_layout.setAlignment(QtCore.Qt.AlignTop)

        title = QtWidgets.QLabel(icon_name)
        title.setObjectName('previewRowTitle')
        meta_layout.addWidget(title)

        relative_path = Icons.relative_path(icon_name)
        path_label = QtWidgets.QLabel(relative_path)
        path_label.setObjectName('previewRowPath')
        path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        meta_layout.addWidget(path_label)

        family = Icons.family(icon_name).title()
        meta = QtWidgets.QLabel(f'{family} icon')
        meta.setObjectName('previewMeta')
        meta_layout.addWidget(meta)
        meta_layout.addStretch(1)

        layout.addLayout(meta_layout, 0)

        swatches = QtWidgets.QHBoxLayout()
        swatches.setSpacing(10)
        for size in Icons.PREVIEW_SIZES:
            swatches.addWidget(self._build_swatch(icon_name, size))
        swatches.addStretch(1)
        layout.addLayout(swatches, 1)

        return frame

    def _build_swatch(self, icon_name, size):
        frame = QtWidgets.QFrame()
        frame.setObjectName('swatchCard')
        frame.setFixedWidth(88)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        preview = QtWidgets.QLabel()
        preview.setAlignment(QtCore.Qt.AlignCenter)
        preview.setMinimumHeight(48)
        pixmap = Icons.pixmap(icon_name, size)
        if not pixmap.isNull():
            preview.setPixmap(pixmap)
        layout.addWidget(preview)

        label = QtWidgets.QLabel(f'{size}px')
        label.setObjectName('swatchSize')
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)

        return frame
