"""
ADS1256 8-Channel Data Acquisition GUI
Professional PyQt5/PyQtGraph interface for real-time data visualization
"""

import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                             QComboBox, QGroupBox, QSpinBox, QCheckBox, 
                             QFileDialog, QStatusBar, QSplitter, QTabWidget,
                             QDoubleSpinBox, QMessageBox)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import pyqtgraph as pg
import numpy as np
from datetime import datetime
import csv

from ads1256_receiver import ADS1256Receiver


class ChannelPlot(QWidget):
    """Individual channel plot with statistics"""
    
    def __init__(self, channel_num, parent=None):
        super().__init__(parent)
        self.channel_num = channel_num
        self.enabled = True
        
        # Colors for each channel
        self.colors = [
            (255, 100, 100),  # Red
            (100, 255, 100),  # Green
            (100, 100, 255),  # Blue
            (255, 255, 100),  # Yellow
            (255, 100, 255),  # Magenta
            (100, 255, 255),  # Cyan
            (255, 165, 0),    # Orange
            (200, 200, 200),  # Gray
        ]
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('k')
        self.plot_widget.setLabel('left', f'Ch{self.channel_num}', units='V')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Plot curve
        pen = pg.mkPen(color=self.colors[self.channel_num], width=1.5)
        self.curve = self.plot_widget.plot(pen=pen)
        
        # Cursors
        self.cursor1 = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('y', width=1, style=Qt.DashLine))
        self.cursor2 = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('y', width=1, style=Qt.DashLine))
        self.cursor1.setVisible(False)
        self.cursor2.setVisible(False)
        self.plot_widget.addItem(self.cursor1)
        self.plot_widget.addItem(self.cursor2)
        
        layout.addWidget(self.plot_widget)
        
        # Statistics panel
        stats_layout = QHBoxLayout()
        self.stats_labels = {}
        
        stats = ['Min', 'Max', 'Mean', 'P-P', 'RMS']
        for stat in stats:
            label = QLabel(f'{stat}: --')
            label.setStyleSheet("color: white; font-size: 9pt;")
            stats_layout.addWidget(label)
            self.stats_labels[stat] = label
        
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        self.setLayout(layout)
    
    def update_plot(self, time_data, voltage_data):
        """Update plot with new data"""
        if self.enabled and len(time_data) > 0:
            self.curve.setData(time_data, voltage_data)
    
    def update_statistics(self, stats):
        """Update statistics display"""
        if stats:
            self.stats_labels['Min'].setText(f"Min: {stats['min']*1000:.2f} mV")
            self.stats_labels['Max'].setText(f"Max: {stats['max']*1000:.2f} mV")
            self.stats_labels['Mean'].setText(f"Mean: {stats['mean']*1000:.2f} mV")
            self.stats_labels['P-P'].setText(f"P-P: {stats['peak_to_peak']*1000:.2f} mV")
            self.stats_labels['RMS'].setText(f"RMS: {stats['rms']*1000:.2f} mV")
    
    def show_cursors(self, show):
        """Show/hide measurement cursors"""
        self.cursor1.setVisible(show)
        self.cursor2.setVisible(show)
    
    def autoscale(self):
        """Auto-scale plot"""
        self.plot_widget.enableAutoRange()


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.receiver = ADS1256Receiver()
        self.is_recording = False
        self.recording_file = None
        self.csv_writer = None
        
        self.init_ui()
        self.init_timers()
        
        # Auto-detect port
        self.refresh_ports()
    
    def init_ui(self):
        self.setWindowTitle('ADS1256 8-Channel Data Acquisition System')
        self.setGeometry(100, 100, 1600, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top control panel
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Splitter for plots and settings
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Plots
        plots_widget = self.create_plots_widget()
        splitter.addWidget(plots_widget)
        
        # Right: Settings panel
        settings_widget = self.create_settings_panel()
        splitter.addWidget(settings_widget)
        
        splitter.setStretchFactor(0, 4)  # Plots take 80%
        splitter.setStretchFactor(1, 1)  # Settings take 20%
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel('Disconnected')
        self.status_bar.addPermanentWidget(self.status_label)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QPushButton {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                padding: 5px 15px;
                border-radius: 3px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:pressed {
                background-color: #2c2c2c;
            }
            QPushButton:disabled {
                background-color: #222222;
                color: #666666;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                padding: 3px;
                border-radius: 3px;
            }
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
    
    def create_control_panel(self):
        """Create top control panel"""
        panel = QGroupBox("Connection & Control")
        layout = QHBoxLayout()
        
        # Port selection
        layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(160)
        layout.addWidget(self.port_combo)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setMaximumWidth(35)
        self.refresh_btn.setToolTip("Обновить список портов")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(self.refresh_btn)

        # Baudrate selection
        layout.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "230400", "460800", "921600"])
        self.baud_combo.setCurrentText("230400")  # Рекомендуемая для STM32 8MHz
        self.baud_combo.setMinimumWidth(85)
        layout.addWidget(self.baud_combo)
        
        layout.addSpacing(10)
        
        # Connection
        self.connect_btn = QPushButton("🔌 Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn)
        
        layout.addSpacing(20)
        
        # Streaming
        self.stream_btn = QPushButton("▶ Start")
        self.stream_btn.clicked.connect(self.toggle_streaming)
        self.stream_btn.setEnabled(False)
        layout.addWidget(self.stream_btn)
        
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        self.paused = False
        layout.addWidget(self.pause_btn)
        
        layout.addSpacing(20)
        
        # Recording
        self.record_btn = QPushButton("⏺ Record")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setEnabled(False)
        layout.addWidget(self.record_btn)
        
        layout.addSpacing(20)
        
        # Cursors
        self.cursor_checkbox = QCheckBox("Show Cursors")
        self.cursor_checkbox.toggled.connect(self.toggle_cursors)
        layout.addWidget(self.cursor_checkbox)
        
        # Auto-scale
        self.autoscale_btn = QPushButton("Auto Scale")
        self.autoscale_btn.clicked.connect(self.autoscale_all)
        layout.addWidget(self.autoscale_btn)
        
        layout.addStretch()
        
        # Statistics
        self.stats_label = QLabel("Packets: 0 | Lost: 0 | Rate: 0 kB/s")
        layout.addWidget(self.stats_label)
        
        panel.setLayout(layout)
        return panel
    
    def create_plots_widget(self):
        """Create 8 channel plots in grid"""
        widget = QWidget()
        layout = QGridLayout()
        layout.setSpacing(5)
        
        self.channel_plots = []
        for i in range(8):
            plot = ChannelPlot(i)
            row = i // 2
            col = i % 2
            layout.addWidget(plot, row, col)
            self.channel_plots.append(plot)
        
        widget.setLayout(layout)
        return widget
    
    def create_settings_panel(self):
        """Create settings panel"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # ADC Settings
        adc_group = QGroupBox("ADC Settings")
        adc_layout = QVBoxLayout()
        
        # PGA Gain
        pga_layout = QHBoxLayout()
        pga_layout.addWidget(QLabel("PGA Gain:"))
        self.pga_combo = QComboBox()
        pga_gains = ['1x', '2x', '4x', '8x', '16x', '32x', '64x']
        self.pga_combo.addItems(pga_gains)
        self.pga_combo.currentIndexChanged.connect(self.change_pga)
        pga_layout.addWidget(self.pga_combo)
        adc_layout.addLayout(pga_layout)
        
        # Data Rate
        drate_layout = QHBoxLayout()
        drate_layout.addWidget(QLabel("Data Rate:"))
        self.drate_combo = QComboBox()
        self.drate_combo.addItems(['2000 SPS', '5000 SPS', '10000 SPS'])
        self.drate_combo.currentIndexChanged.connect(self.change_drate)
        drate_layout.addWidget(self.drate_combo)
        adc_layout.addLayout(drate_layout)
        
        adc_group.setLayout(adc_layout)
        layout.addWidget(adc_group)
        
        # Display Settings
        display_group = QGroupBox("Display Settings")
        display_layout = QVBoxLayout()
        
        # Time window
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time Window:"))
        self.time_window_spin = QDoubleSpinBox()
        self.time_window_spin.setRange(0.5, 60.0)
        self.time_window_spin.setValue(5.0)
        self.time_window_spin.setSuffix(" s")
        time_layout.addWidget(self.time_window_spin)
        display_layout.addLayout(time_layout)
        
        # Channel enable/disable
        self.channel_checkboxes = []
        for i in range(8):
            cb = QCheckBox(f"Channel {i}")
            cb.setChecked(True)
            cb.toggled.connect(lambda checked, ch=i: self.toggle_channel(ch, checked))
            display_layout.addWidget(cb)
            self.channel_checkboxes.append(cb)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        layout.addStretch()
        
        # Device status
        status_group = QGroupBox("Device Status")
        status_layout = QVBoxLayout()
        self.device_status_label = QLabel("Not connected")
        self.device_status_label.setWordWrap(True)
        status_layout.addWidget(self.device_status_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        widget.setLayout(layout)
        return widget
    
    def init_timers(self):
        """Initialize update timers"""
        # Fast update for plots (30 Hz)
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_plots)
        self.plot_timer.start(33)  # ~30 FPS
        
        # Slow update for statistics (2 Hz)
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start(500)  # 2 Hz
    
    def refresh_ports(self):
        """Refresh available COM ports"""
        self.port_combo.clear()
        ports = self.receiver.list_ports()
        
        for port, desc in ports:
            self.port_combo.addItem(f"{port} - {desc}", port)
        
        if len(ports) == 0:
            self.port_combo.addItem("No ports found")
    
    def toggle_connection(self):
        """Connect/disconnect from device"""
        if not self.receiver.is_connected:
            port = self.port_combo.currentData()
            baudrate = int(self.baud_combo.currentText())

            # --- Диагностика перед подключением ---
            if not port:
                QMessageBox.warning(self, "Ошибка",
                    "Порт не выбран.\n\n"
                    "Нажмите 🔄 для обновления списка портов.\n"
                    "Убедитесь, что STM32 подключён по USB.")
                return

            # Устанавливаем baudrate из выпадающего списка
            self.receiver.baudrate = baudrate

            ok, error_msg = self.receiver.connect(port)
            if ok:
                self.connect_btn.setText("🔌 Disconnect")
                self.connect_btn.setStyleSheet("background-color: #1a5c1a;")
                self.stream_btn.setEnabled(True)
                self.baud_combo.setEnabled(False)   # Нельзя менять при подключении
                self.port_combo.setEnabled(False)
                self.status_label.setText(f'✅ {port} @ {baudrate}')
                self.status_label.setStyleSheet("color: lime;")
                self.receiver.get_status()
            else:
                QMessageBox.critical(self, "Ошибка подключения",
                    f"Не удалось открыть порт {port}\n\n"
                    f"Причина: {error_msg}\n\n"
                    "Частые причины:\n"
                    "• Закройте Serial Monitor в Arduino IDE\n"
                    "• Порт занят другой программой\n"
                    "• Неверный COM порт — нажмите 🔄\n"
                    "• Проверьте подключение USB кабеля")
        else:
            self.receiver.disconnect()
            self.connect_btn.setText("🔌 Connect")
            self.connect_btn.setStyleSheet("")
            self.stream_btn.setEnabled(False)
            self.stream_btn.setText("▶ Start")
            self.record_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.baud_combo.setEnabled(True)
            self.port_combo.setEnabled(True)
            self.status_label.setText('Disconnected')
            self.status_label.setStyleSheet("color: #aaaaaa;")
    
    def toggle_streaming(self):
        """Start/stop data streaming"""
        if not self.receiver.is_streaming:
            # Start
            if self.receiver.start_streaming():
                self.stream_btn.setText("⏹ Stop")
                self.record_btn.setEnabled(True)
                self.pause_btn.setEnabled(True)
                self.status_label.setText('Streaming...')
                self.status_label.setStyleSheet("color: lime;")
        else:
            # Stop
            self.receiver.stop_streaming()
            self.stream_btn.setText("▶ Start")
            self.record_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.paused = False
            self.pause_btn.setText("⏸ Pause")
            self.status_label.setText('Connected')
            self.status_label.setStyleSheet("color: green;")
            
            # Stop recording if active
            if self.is_recording:
                self.toggle_recording()
    
    def toggle_pause(self):
        """Pause/resume plotting"""
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.setText("▶ Resume")
            self.plot_timer.stop()
        else:
            self.pause_btn.setText("⏸ Pause")
            self.plot_timer.start(33)
    
    def toggle_recording(self):
        """Start/stop recording to file"""
        if not self.is_recording:
            # Start recording
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Recording", 
                f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv)"
            )
            
            if filename:
                try:
                    self.recording_file = open(filename, 'w', newline='')
                    self.csv_writer = csv.writer(self.recording_file)
                    
                    # Write header
                    header = ['Time (s)'] + [f'Ch{i} (V)' for i in range(8)]
                    self.csv_writer.writerow(header)
                    
                    self.is_recording = True
                    self.record_btn.setText("⏹ Stop Rec")
                    self.record_btn.setStyleSheet("background-color: #cc0000;")
                    self.status_label.setText('Recording...')
                    
                except Exception as e:
                    QMessageBox.critical(self, "Recording Error", str(e))
        else:
            # Stop recording
            if self.recording_file:
                self.recording_file.close()
                self.recording_file = None
                self.csv_writer = None
            
            self.is_recording = False
            self.record_btn.setText("⏺ Record")
            self.record_btn.setStyleSheet("")
            self.status_label.setText('Streaming...')
    
    def toggle_cursors(self, show):
        """Show/hide measurement cursors"""
        for plot in self.channel_plots:
            plot.show_cursors(show)
    
    def autoscale_all(self):
        """Auto-scale all plots"""
        for plot in self.channel_plots:
            plot.autoscale()
    
    def toggle_channel(self, channel, enabled):
        """Enable/disable channel plotting"""
        self.channel_plots[channel].enabled = enabled
    
    def change_pga(self, index):
        """Change PGA gain"""
        if self.receiver.is_connected:
            self.receiver.set_pga(index)
    
    def change_drate(self, index):
        """Change data rate"""
        if self.receiver.is_connected:
            rates = [2000, 5000, 10000]
            self.receiver.set_drate(rates[index])
    
    def update_plots(self):
        """Update all plots with new data"""
        if not self.receiver.is_connected or self.paused:
            return
        
        # Read new data
        new_samples = self.receiver.read_data()
        
        if new_samples > 0:
            # Get data arrays
            time_data, voltage_data = self.receiver.get_data_arrays()
            
            if len(time_data) > 0:
                # Apply time window
                time_window = self.time_window_spin.value()
                current_time = time_data[-1]
                mask = time_data >= (current_time - time_window)
                
                time_plot = time_data[mask]
                
                # Update each channel
                for i in range(8):
                    voltage_plot = voltage_data[i][mask]
                    self.channel_plots[i].update_plot(time_plot, voltage_plot)
                
                # Record to file if active
                if self.is_recording and self.csv_writer:
                    for j in range(len(time_plot)):
                        row = [time_plot[j]] + [voltage_data[i][mask][j] for i in range(8)]
                        self.csv_writer.writerow(row)
    
    def update_statistics(self):
        """Update statistics display"""
        if not self.receiver.is_connected:
            return
        
        # Update channel statistics
        for i in range(8):
            stats = self.receiver.get_statistics(i)
            self.channel_plots[i].update_statistics(stats)
        
        # Update connection statistics
        conn_stats = self.receiver.get_connection_stats()
        
        loss_rate = conn_stats['packet_loss_rate'] * 100
        data_rate_kb = conn_stats['data_rate'] / 1024
        
        stats_text = (f"Packets: {conn_stats['packets_received']} | "
                     f"Lost: {conn_stats['packets_lost']} ({loss_rate:.1f}%) | "
                     f"Rate: {data_rate_kb:.1f} kB/s")
        
        self.stats_label.setText(stats_text)
        
        # Update device status
        if self.receiver.is_streaming:
            elapsed = conn_stats['elapsed_time']
            status_text = (f"Streaming: {elapsed:.1f} s\n"
                          f"Packets: {conn_stats['packets_received']}\n"
                          f"Data: {conn_stats['bytes_received']/1024:.1f} kB")
            self.device_status_label.setText(status_text)
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.receiver.is_connected:
            self.receiver.disconnect()
        
        if self.is_recording and self.recording_file:
            self.recording_file.close()
        
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
