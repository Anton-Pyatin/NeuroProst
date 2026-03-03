"""
ADS1256 Data Analyzer
Offline analysis tool for recorded CSV files
Features: Signal filtering, FFT analysis, statistics, export
"""

import sys
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QFileDialog, QLabel,
                             QComboBox, QCheckBox, QGroupBox, QSpinBox,
                             QDoubleSpinBox, QTabWidget)
from PyQt5.QtCore import Qt
import pyqtgraph as pg
from scipy import signal
from scipy.fft import fft, fftfreq


class DataAnalyzer(QMainWindow):
    """Offline data analysis tool"""
    
    def __init__(self):
        super().__init__()
        self.data = None
        self.filtered_data = None
        self.sample_rate = 250  # Default 250 Hz
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle('ADS1256 Data Analyzer')
        self.setGeometry(100, 100, 1400, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Control panel
        control_layout = QHBoxLayout()
        
        self.load_btn = QPushButton('📂 Load CSV')
        self.load_btn.clicked.connect(self.load_file)
        control_layout.addWidget(self.load_btn)
        
        control_layout.addWidget(QLabel('Sample Rate:'))
        self.sample_rate_spin = QSpinBox()
        self.sample_rate_spin.setRange(1, 10000)
        self.sample_rate_spin.setValue(250)
        self.sample_rate_spin.setSuffix(' Hz')
        self.sample_rate_spin.valueChanged.connect(self.update_sample_rate)
        control_layout.addWidget(self.sample_rate_spin)
        
        self.export_btn = QPushButton('💾 Export Filtered')
        self.export_btn.clicked.connect(self.export_filtered)
        self.export_btn.setEnabled(False)
        control_layout.addWidget(self.export_btn)
        
        control_layout.addStretch()
        
        self.info_label = QLabel('No data loaded')
        control_layout.addWidget(self.info_label)
        
        main_layout.addLayout(control_layout)
        
        # Tabs
        tabs = QTabWidget()
        
        # Tab 1: Time domain
        time_tab = QWidget()
        time_layout = QVBoxLayout(time_tab)
        
        time_controls = self.create_filter_controls()
        time_layout.addWidget(time_controls)
        
        self.time_plot = pg.PlotWidget()
        self.time_plot.setBackground('k')
        self.time_plot.setLabel('left', 'Voltage', units='V')
        self.time_plot.setLabel('bottom', 'Time', units='s')
        self.time_plot.showGrid(x=True, y=True, alpha=0.3)
        time_layout.addWidget(self.time_plot)
        
        tabs.addTab(time_tab, "Time Domain")
        
        # Tab 2: Frequency domain
        freq_tab = QWidget()
        freq_layout = QVBoxLayout(freq_tab)
        
        freq_controls = QHBoxLayout()
        freq_controls.addWidget(QLabel('Channel:'))
        self.fft_channel_combo = QComboBox()
        self.fft_channel_combo.addItems([f'Ch{i}' for i in range(8)])
        self.fft_channel_combo.currentIndexChanged.connect(self.update_fft)
        freq_controls.addWidget(self.fft_channel_combo)
        
        self.fft_window_combo = QComboBox()
        self.fft_window_combo.addItems(['None', 'Hanning', 'Hamming', 'Blackman'])
        self.fft_window_combo.currentIndexChanged.connect(self.update_fft)
        freq_controls.addWidget(self.fft_window_combo)
        
        freq_controls.addStretch()
        freq_layout.addLayout(freq_controls)
        
        self.fft_plot = pg.PlotWidget()
        self.fft_plot.setBackground('k')
        self.fft_plot.setLabel('left', 'Magnitude', units='dB')
        self.fft_plot.setLabel('bottom', 'Frequency', units='Hz')
        self.fft_plot.showGrid(x=True, y=True, alpha=0.3)
        self.fft_plot.setLogMode(x=False, y=False)
        freq_layout.addWidget(self.fft_plot)
        
        tabs.addTab(freq_tab, "FFT Analysis")
        
        # Tab 3: Statistics
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        
        self.stats_table_widget = QWidget()
        stats_table_layout = QVBoxLayout(self.stats_table_widget)
        self.stats_label = QLabel('Load data to see statistics')
        self.stats_label.setWordWrap(True)
        stats_table_layout.addWidget(self.stats_label)
        stats_table_layout.addStretch()
        stats_layout.addWidget(self.stats_table_widget)
        
        tabs.addTab(stats_tab, "Statistics")
        
        main_layout.addWidget(tabs)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QPushButton {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                padding: 3px;
            }
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
        """)
    
    def create_filter_controls(self):
        """Create filter control panel"""
        group = QGroupBox("Signal Processing")
        layout = QHBoxLayout()
        
        # Filter type
        layout.addWidget(QLabel('Filter:'))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['None', 'Lowpass', 'Highpass', 'Bandpass', 'Bandstop'])
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_combo)
        
        # Cutoff frequency
        layout.addWidget(QLabel('Cutoff:'))
        self.cutoff_spin = QDoubleSpinBox()
        self.cutoff_spin.setRange(0.1, 5000)
        self.cutoff_spin.setValue(50)
        self.cutoff_spin.setSuffix(' Hz')
        self.cutoff_spin.valueChanged.connect(self.apply_filter)
        layout.addWidget(self.cutoff_spin)
        
        # Filter order
        layout.addWidget(QLabel('Order:'))
        self.order_spin = QSpinBox()
        self.order_spin.setRange(1, 10)
        self.order_spin.setValue(4)
        self.order_spin.valueChanged.connect(self.apply_filter)
        layout.addWidget(self.order_spin)
        
        # Channel selection
        layout.addWidget(QLabel('Channel:'))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems([f'Ch{i}' for i in range(8)])
        self.channel_combo.currentIndexChanged.connect(self.update_plot)
        layout.addWidget(self.channel_combo)
        
        # Show original
        self.show_original_cb = QCheckBox('Show Original')
        self.show_original_cb.setChecked(True)
        self.show_original_cb.toggled.connect(self.update_plot)
        layout.addWidget(self.show_original_cb)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def load_file(self):
        """Load CSV file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Recording", "", "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                # Load CSV
                self.data = pd.read_csv(filename)
                
                # Validate format
                expected_cols = ['Time (s)'] + [f'Ch{i} (V)' for i in range(8)]
                if not all(col in self.data.columns for col in expected_cols):
                    raise ValueError("Invalid CSV format. Expected columns: " + str(expected_cols))
                
                # Extract time and channel data
                self.time = self.data['Time (s)'].values
                self.channels = [self.data[f'Ch{i} (V)'].values for i in range(8)]
                
                # Calculate actual sample rate
                if len(self.time) > 1:
                    dt = np.mean(np.diff(self.time))
                    calculated_rate = int(1.0 / dt)
                    self.sample_rate_spin.setValue(calculated_rate)
                
                self.filtered_data = None
                
                # Update info
                duration = self.time[-1] - self.time[0]
                self.info_label.setText(
                    f'Loaded: {len(self.time)} samples, {duration:.1f} s, '
                    f'{self.sample_rate} Hz'
                )
                
                self.export_btn.setEnabled(True)
                
                # Update displays
                self.update_plot()
                self.update_fft()
                self.update_statistics()
                
            except Exception as e:
                self.info_label.setText(f'Error loading file: {e}')
    
    def update_sample_rate(self, rate):
        """Update sample rate"""
        self.sample_rate = rate
        if self.data is not None:
            self.update_fft()
    
    def apply_filter(self):
        """Apply digital filter to data"""
        if self.data is None:
            return
        
        filter_type = self.filter_combo.currentText()
        
        if filter_type == 'None':
            self.filtered_data = None
            self.update_plot()
            return
        
        try:
            # Design filter
            nyquist = self.sample_rate / 2
            cutoff = self.cutoff_spin.value()
            order = self.order_spin.value()
            
            if cutoff >= nyquist:
                self.info_label.setText(f'Error: Cutoff must be < {nyquist} Hz')
                return
            
            if filter_type == 'Lowpass':
                sos = signal.butter(order, cutoff / nyquist, 'lowpass', output='sos')
            elif filter_type == 'Highpass':
                sos = signal.butter(order, cutoff / nyquist, 'highpass', output='sos')
            elif filter_type == 'Bandpass':
                # For bandpass, use cutoff as center, bandwidth = cutoff/2
                low = max(0.1, cutoff - cutoff/4)
                high = min(nyquist - 0.1, cutoff + cutoff/4)
                sos = signal.butter(order, [low / nyquist, high / nyquist], 'bandpass', output='sos')
            elif filter_type == 'Bandstop':
                low = max(0.1, cutoff - cutoff/4)
                high = min(nyquist - 0.1, cutoff + cutoff/4)
                sos = signal.butter(order, [low / nyquist, high / nyquist], 'bandstop', output='sos')
            
            # Apply filter to all channels
            self.filtered_data = []
            for ch_data in self.channels:
                filtered = signal.sosfilt(sos, ch_data)
                self.filtered_data.append(filtered)
            
            self.update_plot()
            
        except Exception as e:
            self.info_label.setText(f'Filter error: {e}')
    
    def update_plot(self):
        """Update time domain plot"""
        if self.data is None:
            return
        
        self.time_plot.clear()
        
        channel = self.channel_combo.currentIndex()
        
        # Plot original
        if self.show_original_cb.isChecked():
            pen = pg.mkPen(color=(100, 100, 255), width=1)
            self.time_plot.plot(self.time, self.channels[channel], pen=pen, name='Original')
        
        # Plot filtered
        if self.filtered_data is not None:
            pen = pg.mkPen(color=(255, 100, 100), width=1.5)
            self.time_plot.plot(self.time, self.filtered_data[channel], pen=pen, name='Filtered')
    
    def update_fft(self):
        """Update FFT plot"""
        if self.data is None:
            return
        
        channel = self.fft_channel_combo.currentIndex()
        window_type = self.fft_window_combo.currentText()
        
        # Use filtered data if available
        if self.filtered_data is not None:
            data = self.filtered_data[channel]
        else:
            data = self.channels[channel]
        
        # Remove DC component
        data = data - np.mean(data)
        
        # Apply window
        if window_type == 'Hanning':
            window = np.hanning(len(data))
        elif window_type == 'Hamming':
            window = np.hamming(len(data))
        elif window_type == 'Blackman':
            window = np.blackman(len(data))
        else:
            window = np.ones(len(data))
        
        data_windowed = data * window
        
        # Compute FFT
        N = len(data_windowed)
        yf = fft(data_windowed)
        xf = fftfreq(N, 1/self.sample_rate)[:N//2]
        
        # Compute magnitude in dB
        magnitude = 2.0/N * np.abs(yf[:N//2])
        magnitude_db = 20 * np.log10(magnitude + 1e-10)  # Add small value to avoid log(0)
        
        # Plot
        self.fft_plot.clear()
        pen = pg.mkPen(color=(100, 255, 100), width=1.5)
        self.fft_plot.plot(xf, magnitude_db, pen=pen)
    
    def update_statistics(self):
        """Update statistics table"""
        if self.data is None:
            return
        
        stats_text = "<h3>Channel Statistics</h3><table border='1' style='border-collapse: collapse;'>"
        stats_text += "<tr><th>Ch</th><th>Min (mV)</th><th>Max (mV)</th><th>Mean (mV)</th><th>Std (mV)</th><th>P-P (mV)</th><th>RMS (mV)</th></tr>"
        
        for i in range(8):
            data = self.channels[i]
            min_val = np.min(data) * 1000
            max_val = np.max(data) * 1000
            mean_val = np.mean(data) * 1000
            std_val = np.std(data) * 1000
            pp_val = (max_val - min_val)
            rms_val = np.sqrt(np.mean(data**2)) * 1000
            
            stats_text += f"<tr><td>{i}</td><td>{min_val:.2f}</td><td>{max_val:.2f}</td>"
            stats_text += f"<td>{mean_val:.2f}</td><td>{std_val:.2f}</td><td>{pp_val:.2f}</td><td>{rms_val:.2f}</td></tr>"
        
        stats_text += "</table>"
        
        self.stats_label.setText(stats_text)
    
    def export_filtered(self):
        """Export filtered data to CSV"""
        if self.filtered_data is None:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Filtered Data", "", "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                # Create DataFrame
                export_data = {'Time (s)': self.time}
                for i in range(8):
                    export_data[f'Ch{i} (V)'] = self.filtered_data[i]
                
                df = pd.DataFrame(export_data)
                df.to_csv(filename, index=False)
                
                self.info_label.setText(f'Exported to: {filename}')
            except Exception as e:
                self.info_label.setText(f'Export error: {e}')


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = DataAnalyzer()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
