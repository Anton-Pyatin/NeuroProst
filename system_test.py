"""
ADS1256 System Test & Calibration Utility
Automated tests for hardware validation
"""

import serial
import serial.tools.list_ports
import time
import numpy as np
import struct


class SystemTester:
    """Hardware testing and calibration utility"""
    
    SYNC_BYTE1 = 0xAA
    SYNC_BYTE2 = 0x55
    CHANNELS = 8
    VREF = 2.5
    
    def __init__(self, port=None, baudrate=921600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
    
    def list_ports(self):
        """List available COM ports"""
        ports = serial.tools.list_ports.comports()
        print("\n=== Available COM Ports ===")
        for i, p in enumerate(ports):
            print(f"{i}: {p.device} - {p.description}")
        return ports
    
    def connect(self, port=None):
        """Connect to device"""
        if port:
            self.port = port
        
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            time.sleep(2)  # Wait for reset
            
            # Clear buffer
            self.serial.reset_input_buffer()
            
            print(f"\n✓ Connected to {self.port}")
            return True
            
        except Exception as e:
            print(f"\n✗ Connection failed: {e}")
            return False
    
    def send_command(self, cmd, wait_response=True):
        """Send command and get response"""
        self.serial.write(f"{cmd}\n".encode())
        time.sleep(0.1)
        
        if wait_response:
            response = self.serial.read(self.serial.in_waiting).decode()
            return response
        return None
    
    def test_communication(self):
        """Test 1: Basic communication"""
        print("\n" + "="*50)
        print("TEST 1: Communication Test")
        print("="*50)
        
        response = self.send_command("STATUS")
        
        if "STATUS:" in response or "STREAMING" in response:
            print("✓ Communication OK")
            print(f"Response:\n{response}")
            return True
        else:
            print("✗ Communication FAILED")
            print(f"Response: {response}")
            return False
    
    def test_streaming(self, duration=5):
        """Test 2: Data streaming"""
        print("\n" + "="*50)
        print(f"TEST 2: Streaming Test ({duration}s)")
        print("="*50)
        
        # Start streaming
        self.send_command("START", wait_response=False)
        time.sleep(0.5)
        
        packets_received = 0
        bytes_received = 0
        start_time = time.time()
        last_packet_num = -1
        packets_lost = 0
        
        print("Receiving data...")
        
        while time.time() - start_time < duration:
            if self.serial.in_waiting > 0:
                data = self.serial.read(self.serial.in_waiting)
                bytes_received += len(data)
                
                # Find sync pattern
                for i in range(len(data) - 1):
                    if data[i] == self.SYNC_BYTE1 and data[i+1] == self.SYNC_BYTE2:
                        # Found packet
                        if i + 4 < len(data):
                            packet_num = struct.unpack('>H', data[i+2:i+4])[0]
                            
                            # Check for lost packets
                            if last_packet_num >= 0:
                                expected = (last_packet_num + 1) % 65536
                                if packet_num != expected:
                                    lost = (packet_num - expected) % 65536
                                    packets_lost += lost
                            
                            last_packet_num = packet_num
                            packets_received += 1
        
        # Stop streaming
        self.send_command("STOP")
        
        elapsed = time.time() - start_time
        packet_rate = packets_received / elapsed
        data_rate = bytes_received / elapsed / 1024  # kB/s
        loss_rate = packets_lost / max(1, packets_received + packets_lost) * 100
        
        print(f"\nResults:")
        print(f"  Duration: {elapsed:.1f} s")
        print(f"  Packets received: {packets_received}")
        print(f"  Packets lost: {packets_lost} ({loss_rate:.2f}%)")
        print(f"  Packet rate: {packet_rate:.1f} pkt/s")
        print(f"  Data rate: {data_rate:.1f} kB/s")
        
        if loss_rate < 1.0:
            print("✓ Streaming OK")
            return True
        elif loss_rate < 5.0:
            print("⚠ Streaming MARGINAL (high packet loss)")
            return True
        else:
            print("✗ Streaming FAILED (excessive packet loss)")
            return False
    
    def test_noise_floor(self, duration=3):
        """Test 3: Noise floor measurement"""
        print("\n" + "="*50)
        print(f"TEST 3: Noise Floor ({duration}s)")
        print("="*50)
        print("⚠ Connect all inputs to GND for this test")
        input("Press Enter when ready...")
        
        # Start streaming
        self.send_command("START", wait_response=False)
        time.sleep(0.5)
        
        channel_data = [[] for _ in range(self.CHANNELS)]
        start_time = time.time()
        
        print("Measuring noise...")
        
        while time.time() - start_time < duration:
            if self.serial.in_waiting > 0:
                data = self.serial.read(self.serial.in_waiting)
                
                # Find and parse packets
                for i in range(len(data) - 1):
                    if data[i] == self.SYNC_BYTE1 and data[i+1] == self.SYNC_BYTE2:
                        if i + 5 < len(data):
                            sample_count = data[i+4]
                            packet_size = 5 + (sample_count * self.CHANNELS * 4) + 1
                            
                            if i + packet_size <= len(data):
                                packet = data[i:i+packet_size]
                                
                                # Parse data
                                data_start = 5
                                for s in range(sample_count):
                                    for ch in range(self.CHANNELS):
                                        idx = data_start + (s * self.CHANNELS + ch) * 4
                                        if idx + 4 <= len(packet):
                                            raw = struct.unpack('>i', packet[idx:idx+4])[0]
                                            voltage = (raw * 2.0 * self.VREF) / 8388608.0
                                            channel_data[ch].append(voltage * 1000)  # mV
        
        # Stop streaming
        self.send_command("STOP")
        
        # Calculate statistics
        print("\nNoise Floor Results (inputs grounded):")
        print(f"{'Ch':<4} {'Mean (mV)':<12} {'Std (mV)':<12} {'P-P (mV)':<12} {'RMS (μV)':<12}")
        print("-" * 52)
        
        all_good = True
        for ch in range(self.CHANNELS):
            if len(channel_data[ch]) > 0:
                data_array = np.array(channel_data[ch])
                mean = np.mean(data_array)
                std = np.std(data_array)
                pp = np.max(data_array) - np.min(data_array)
                rms = np.sqrt(np.mean(data_array**2)) * 1000  # μV
                
                print(f"{ch:<4} {mean:>10.3f}  {std:>10.3f}  {pp:>10.3f}  {rms:>10.1f}")
                
                # Check thresholds
                if std > 0.1 or pp > 0.5:  # 100 μV std, 500 μV p-p
                    all_good = False
        
        if all_good:
            print("\n✓ Noise floor GOOD")
        else:
            print("\n⚠ Noise floor HIGH - check grounding and shielding")
        
        return all_good
    
    def test_input_range(self):
        """Test 4: Input range verification"""
        print("\n" + "="*50)
        print("TEST 4: Input Range Test")
        print("="*50)
        print("⚠ This test requires a known voltage source")
        print("  Connect a stable voltage (0.5V - 2.0V) to Channel 0")
        
        voltage_input = input("Enter applied voltage (V): ")
        try:
            expected_voltage = float(voltage_input)
        except:
            print("Invalid input")
            return False
        
        # Start streaming
        self.send_command("START", wait_response=False)
        time.sleep(1)
        
        ch0_data = []
        
        for _ in range(20):  # Collect 20 samples
            if self.serial.in_waiting > 0:
                data = self.serial.read(self.serial.in_waiting)
                
                # Parse first channel only
                for i in range(len(data) - 1):
                    if data[i] == self.SYNC_BYTE1 and data[i+1] == self.SYNC_BYTE2:
                        if i + 9 < len(data):
                            sample_count = data[i+4]
                            data_start = 5
                            
                            raw = struct.unpack('>i', data[i+data_start:i+data_start+4])[0]
                            voltage = (raw * 2.0 * self.VREF) / 8388608.0
                            ch0_data.append(voltage)
                            
                            if len(ch0_data) >= 20:
                                break
            time.sleep(0.1)
        
        self.send_command("STOP")
        
        if len(ch0_data) > 0:
            measured = np.mean(ch0_data)
            error = abs(measured - expected_voltage)
            error_percent = (error / expected_voltage) * 100
            
            print(f"\nResults:")
            print(f"  Expected: {expected_voltage:.4f} V")
            print(f"  Measured: {measured:.4f} V")
            print(f"  Error: {error*1000:.2f} mV ({error_percent:.2f}%)")
            
            if error_percent < 1.0:
                print("✓ Accuracy EXCELLENT")
                return True
            elif error_percent < 5.0:
                print("⚠ Accuracy ACCEPTABLE")
                return True
            else:
                print("✗ Accuracy POOR - check VREF and calibration")
                return False
        else:
            print("✗ No data received")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("  ADS1256 SYSTEM TEST SUITE")
        print("="*70)
        
        results = {}
        
        # Test 1: Communication
        results['Communication'] = self.test_communication()
        
        if results['Communication']:
            # Test 2: Streaming
            results['Streaming'] = self.test_streaming(duration=5)
            
            # Test 3: Noise floor
            results['Noise Floor'] = self.test_noise_floor(duration=3)
            
            # Test 4: Input range
            do_range_test = input("\nRun input range test? (y/n): ")
            if do_range_test.lower() == 'y':
                results['Input Range'] = self.test_input_range()
        
        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        for test_name, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{test_name:<20} {status}")
        
        all_passed = all(results.values())
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED - System is ready!")
        else:
            print("\n⚠ SOME TESTS FAILED - Check hardware and connections")
        
        return all_passed


def main():
    """Main function"""
    tester = SystemTester()
    
    # List ports
    ports = tester.list_ports()
    
    if len(ports) == 0:
        print("\n✗ No COM ports found!")
        return
    
    # Select port
    try:
        port_idx = int(input("\nSelect port number: "))
        selected_port = ports[port_idx].device
    except:
        print("Invalid selection")
        return
    
    # Connect
    if not tester.connect(selected_port):
        return
    
    # Run tests
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n✗ Error during tests: {e}")
    finally:
        if tester.serial:
            tester.serial.close()
            print("\nDisconnected")


if __name__ == '__main__':
    main()
