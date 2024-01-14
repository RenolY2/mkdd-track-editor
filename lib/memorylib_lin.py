#!/usr/bin/env python3
"""
Module that provides functionality for hooking the MKDD Track Editor into Dolphin.

This module is used as a client-server application. In order to read/write from/to Dolphin's
memory, elevated permissions are required. To avoid coupling the permissions with the MKDD Track
Editor, a separate process (the Dolphin Hook server) is used to manage memory reads and writes. The
MKDD Track Editor will communicate with the server via a TCP socket.

To enable hooking into Dolphin in MKDD Track Editor in Linux, the server side needs to be started
with elevated permissions in advance:

    sudo python3 "/path/to/memorylib_lin.py"

This code has been adapted from https://github.com/RenolY2/dolphin-memory-lib/blob/memtest_lin.py,
which included the following note as well:

    The following code is a port of aldelaro5's Dolphin memory access methods
    for Linux into Python+ctypes.
    https://github.com/aldelaro5/Dolphin-memory-engine

    MIT License

    Copyright (c) 2017 aldelaro5

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""

import ctypes
import os
import socket
import struct
import subprocess
import tempfile

try:
    from vectors import Vector3
except ImportError:
    from .vectors import Vector3


class iovec(ctypes.Structure):
    _fields_ = [('iov_base', ctypes.c_void_p), ('iov_len', ctypes.c_size_t)]


libc = ctypes.cdll.LoadLibrary('libc.so.6')
vm = libc.process_vm_readv
vm.argtypes = [
    ctypes.c_int,
    ctypes.POINTER(iovec),
    ctypes.c_ulong,
    ctypes.POINTER(iovec),
    ctypes.c_ulong,
    ctypes.c_ulong,
]
vmwrite = libc.process_vm_writev
vmwrite.argtypes = [
    ctypes.c_int,
    ctypes.POINTER(iovec),
    ctypes.c_ulong,
    ctypes.POINTER(iovec),
    ctypes.c_ulong,
    ctypes.c_ulong,
]


class DolphinProxy:

    def __init__(self):
        self.pid = -1
        self.handle = -1

        self.address_start = 0
        self.mem1_start = 0
        self.mem2_start = 0
        self.mem2_exists = False

    def reset(self):
        self.pid = -1
        self.handle = -1

        self.address_start = 0
        self.mem1_start = 0
        self.mem2_start = 0
        self.mem2_exists = False

    def initialized(self):
        return self.address_start != 0

    def address_valid(self, addr):
        try:
            return 0x80000000 <= addr <= 0x81FFFFFF
        except TypeError:
            return False

    def find_dolphin(self):
        self.pid = -1

        DOLPHIN_PROCESS_NAMES = (
            'dolphin-emu',
            'dolphin-emu-qt2',
            'dolphin-emu-wx',
        )
        for process_name in DOLPHIN_PROCESS_NAMES:
            try:
                result = subprocess.check_output(('pidof', process_name))
            except subprocess.CalledProcessError:
                result = None
            if result:
                try:
                    self.pid = int(result)
                    break
                except (TypeError, ValueError, OverflowError):
                    pass

        return self.pid != -1

    def __get_emu_info(self):
        try:
            maps_file = open(f"/proc/{self.pid}/maps".format(), 'r', encoding='ascii')
        except IOError:
            print(f"Cant open maps for process {self.pid}")

        heap_info = None
        for line in maps_file:
            if '/dev/shm/dolphinmem' in line:
                heap_info = line.split()
            if '/dev/shm/dolphin-emu' in line:
                heap_info = line.split()
            if heap_info is None:
                continue

            offset = 0
            offset_str = "0x" + str(heap_info[2])
            offset = int(offset_str, 16)
            if offset != 0 and offset != 0x2000000:
                continue
            first_address = 0
            second_address = 0
            index_dash = heap_info[0].find('-')

            first_address_str = "0x" + str(heap_info[0][:index_dash])
            second_address_str = "0x" + str(heap_info[0][(index_dash + 1):])

            first_address = int(first_address_str, 16)
            second_address = int(second_address_str, 16)

            if (second_address - first_address) == 0x4000000 and offset == 0x2000000:
                self.mem2_start = first_address
                self.mem2_exists = True
            if (second_address - first_address) == 0x2000000 and offset == 0x0:
                self.address_start = first_address

        return self.address_start != 0

    def init(self):
        return self.__get_emu_info()

    def read_ram(self, offset, size):
        buffer_ = (ctypes.c_char * size)()
        nread = ctypes.c_size_t
        local = (iovec * 1)()
        remote = (iovec * 1)()
        local[0].iov_base = ctypes.addressof(buffer_)
        local[0].iov_len = size
        remote[0].iov_base = ctypes.c_void_p(self.address_start + offset)
        remote[0].iov_len = size
        nread = vm(self.pid, local, 1, remote, 1, 0)
        if nread != size:
            return False, buffer_
        return True, buffer_

    def write_ram(self, offset, data):
        buffer_ = (ctypes.c_char * len(data))(*data)
        nwrote = ctypes.c_size_t
        local = (iovec * 1)()
        remote = (iovec * 1)()
        local[0].iov_base = ctypes.addressof(buffer_)
        local[0].iov_len = len(data)
        remote[0].iov_base = ctypes.c_void_p(self.address_start + offset)
        remote[0].iov_len = len(data)
        nwrote = vmwrite(self.pid, local, 1, remote, 1, 0)
        if nwrote != len(data):
            return False
        return True

    def read_uint32(self, addr):
        assert addr >= 0x80000000
        success, value = self.read_ram(addr - 0x80000000, 4)

        if success:
            return struct.unpack(">I", value)[0]

        return None

    def write_uint32(self, addr, val):
        assert addr >= 0x80000000
        return self.write_ram(addr - 0x80000000, struct.pack(">I", val))

    def read_float(self, addr):
        assert addr >= 0x80000000
        success, value = self.read_ram(addr - 0x80000000, 4)

        if success:
            return struct.unpack(">f", value)[0]

        return None

    def write_float(self, addr, val):
        assert addr >= 0x80000000
        return self.write_ram(addr - 0x80000000, struct.pack(">f", val))

    def read_ushort(self, addr):
        assert addr >= 0x80000000
        success, value = self.read_ram(addr - 0x80000000, 4)

        if success:
            return struct.unpack(">H", value)[0]

        return None

    def write_ushort(self, addr, val):
        assert addr >= 0x80000000
        return self.write_ram(addr - 0x80000000, struct.pack(">H", val))

    def read_vector(self, addr):
        assert addr >= 0x80000000
        success, value = self.read_ram(addr - 0x80000000, 12)

        if success:
            return struct.unpack(">fff", value)

        return None

    def write_vector(self, addr, val):
        assert addr >= 0x80000000
        return self.write_ram(addr - 0x80000000, struct.pack(">fff", *val))


HOST = '127.0.0.1'
PORT = 0
MAGIC_NUMBER = b'1717'
MAX_DATA_LENGTH = 4096
PORT_TEMP_FILENAME = 'mkdd_track_editor_dolphinserver_port.txt'

COMMAND_FIND_DOLPHIN = 0x00
COMMAND_INIT = 0x01
COMMAND_READ_RAM = 0x02
COMMAND_WRITE_RAM = 0x03
COMMAND_READ_UINT32 = 0x04
COMMAND_WRITE_UINT32 = 0x05
COMMAND_READ_FLOAT = 0x06
COMMAND_WRITE_FLOAT = 0x07
COMMAND_READ_UINT16 = 0x08
COMMAND_WRITE_UINT16 = 0x09
COMMAND_READ_VECTOR = 0x0A
COMMAND_WRITE_VECTOR = 0x0B

port_temp_filepath = os.path.join(tempfile.gettempdir(), PORT_TEMP_FILENAME)


class DolphinServer:

    def __init__(self):
        self.dolphin_proxy = DolphinProxy()

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            port = s.getsockname()[1]

            with open(port_temp_filepath, 'w', encoding='ascii') as f:
                f.write(str(port))
            print(f'Server listening on {port}.')

            while True:
                print('Waiting for client...')
                conn, addr = s.accept()
                with conn:
                    print(f'Connected by {addr[0]}:{addr[1]}.')
                    while True:
                        try:
                            input_data = conn.recv(MAX_DATA_LENGTH)
                            if not input_data:
                                break
                            output_data = self._process_command(input_data)
                            conn.sendall(output_data)
                        except ConnectionError:
                            break
                    print('Disconnected.')

    def _process_command(self, input_data: bytes) -> bytes:
        return_code = 0
        error_message = ''
        result = bytes()

        try:
            if input_data.startswith(MAGIC_NUMBER):
                command_type = input_data[4]
                if command_type == COMMAND_FIND_DOLPHIN:
                    print('find_dolphin()')
                    return_code = 0 if self.dolphin_proxy.find_dolphin() else 1
                    if return_code != 0:
                        error_message = 'Unable to find Dolphin.'

                elif command_type == COMMAND_INIT:
                    print('init()')
                    return_code = 0 if self.dolphin_proxy.init() else 1
                    if return_code != 0:
                        error_message = ('Unable to initialize. Is server running with sudo '
                                         'permissions? Is game running?')

                elif command_type == COMMAND_READ_RAM:
                    offset, size = struct.unpack('>QQ', input_data[5 + 0:])

                    ok, buffer_ = self.dolphin_proxy.read_ram(offset, size)
                    if ok:
                        result = bytes(buffer_)
                    else:
                        return_code = 8
                        error_message = 'Unable to read memory'

                elif command_type == COMMAND_WRITE_RAM:
                    offset = struct.unpack('>Q', input_data[5 + 0:5 + 8])[0]
                    data = input_data[5 + 8:]

                    ok = self.dolphin_proxy.write_ram(offset, data)
                    if not ok:
                        return_code = 9
                        error_message = 'Unable to write memory'

                elif command_type == COMMAND_READ_UINT32:
                    addr = struct.unpack('>Q', input_data[5 + 0:])[0]

                    value = self.dolphin_proxy.read_uint32(addr)
                    if value is not None:
                        result = struct.pack('>I', value)
                    else:
                        return_code = 10
                        error_message = 'Unable to read unsigned int'

                elif command_type == COMMAND_WRITE_UINT32:
                    addr, value = struct.unpack('>QI', input_data[5 + 0:])

                    ok = self.dolphin_proxy.write_uint32(addr, value)
                    if not ok:
                        return_code = 11
                        error_message = 'Unable to write unsigned int'

                elif command_type == COMMAND_READ_FLOAT:
                    addr = struct.unpack('>Q', input_data[5 + 0:])[0]

                    value = self.dolphin_proxy.read_float(addr)
                    if value is not None:
                        result = struct.pack('>f', value)
                    else:
                        return_code = 12
                        error_message = 'Unable to read float'

                elif command_type == COMMAND_WRITE_FLOAT:
                    addr, value = struct.unpack('>Qf', input_data[5 + 0:])

                    ok = self.dolphin_proxy.write_float(addr, value)
                    if not ok:
                        return_code = 13
                        error_message = 'Unable to write float'

                elif command_type == COMMAND_READ_UINT16:
                    addr = struct.unpack('>Q', input_data[5 + 0:])[0]

                    value = self.dolphin_proxy.read_ushort(addr)
                    if value is not None:
                        result = struct.pack('>H', value)
                    else:
                        return_code = 14
                        error_message = 'Unable to read ushort'

                elif command_type == COMMAND_WRITE_UINT16:
                    addr, value = struct.unpack('>QH', input_data[5 + 0:])

                    ok = self.dolphin_proxy.write_ushort(addr, value)
                    if not ok:
                        return_code = 15
                        error_message = 'Unable to write ushort'

                elif command_type == COMMAND_READ_VECTOR:
                    addr = struct.unpack('>Q', input_data[5 + 0:])[0]

                    value = self.dolphin_proxy.read_vector(addr)
                    if value is not None:
                        result = struct.pack('>fff', *value)
                    else:
                        return_code = 16
                        error_message = 'Unable to read vector'

                elif command_type == COMMAND_WRITE_VECTOR:
                    addr, *value = struct.unpack('>Qfff', input_data[5 + 0:])

                    ok = self.dolphin_proxy.write_vector(addr, value)
                    if not ok:
                        return_code = 17
                        error_message = 'Unable to write vector'

                else:
                    return_code = 3
                    error_message = f'Unknown command type: {command_type}'
                    print(error_message)
            else:
                return_code = 2
                error_message = 'Bad magic number'
        except Exception as e:  # pylint: disable=broad-except
            return_code = 1
            error_message = str(e) or f'Unexpected {type(e)} exception'

        if return_code:
            output_data = MAGIC_NUMBER + bytes((return_code, )) + error_message.encode('utf-8')
        else:
            output_data = MAGIC_NUMBER + bytes((return_code, )) + result

        return output_data


class DolphinClient:

    def __init__(self):
        self.__socket = None
        self.__initialized = False

    def reset(self):
        self.__socket = None
        self.__initialized = False

    def address_valid(self, addr):
        try:
            return 0x80000000 <= addr <= 0x81FFFFFF
        except TypeError:
            return False

    def find_dolphin(self):
        if not self.__connect():
            return False

        output_data = MAGIC_NUMBER + bytes((COMMAND_FIND_DOLPHIN, ))

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to find Dolphin: {error_message}')

        return return_code == 0

    def init(self):
        if not self.__connect():
            return False

        output_data = MAGIC_NUMBER + bytes((COMMAND_INIT, ))

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to intialize: {error_message}')
            self.__initialized = False
        else:
            self.__initialized = True

        return self.__initialized

    def initialized(self):
        return self.__initialized

    def read_ram(self, offset, size):
        output_data = MAGIC_NUMBER + bytes((COMMAND_READ_RAM, ))
        output_data += struct.pack('>Q', offset) + struct.pack('>Q', size)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to read memory: {error_message}')
            return None

        return result

    def write_ram(self, offset, data):
        output_data = MAGIC_NUMBER + bytes((COMMAND_WRITE_RAM, ))
        output_data += struct.pack('>Q', offset) + data

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to write memory: {error_message}')

        return return_code == 0

    def read_uint32(self, addr):
        output_data = MAGIC_NUMBER + bytes((COMMAND_READ_UINT32, ))
        output_data += struct.pack('>Q', addr)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to read unsigned int: {error_message}')
            return None

        return struct.unpack('>I', result)[0]

    def write_uint32(self, addr, val):
        output_data = MAGIC_NUMBER + bytes((COMMAND_WRITE_UINT32, ))
        output_data += struct.pack('>Q', addr) + struct.pack('>I', val)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to write unsigned int: {error_message}')

        return return_code == 0

    def read_float(self, addr):
        output_data = MAGIC_NUMBER + bytes((COMMAND_READ_FLOAT, ))
        output_data += struct.pack('>Q', addr)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to read float: {error_message}')
            return None

        return struct.unpack('>f', result)[0]

    def write_float(self, addr, val):
        output_data = MAGIC_NUMBER + bytes((COMMAND_WRITE_FLOAT, ))
        output_data += struct.pack('>Q', addr) + struct.pack('>f', val)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to write float: {error_message}')

        return return_code == 0

    def read_ushort(self, addr):
        output_data = MAGIC_NUMBER + bytes((COMMAND_READ_UINT16, ))
        output_data += struct.pack('>Q', addr)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to read ushort: {error_message}')
            return None

        return struct.unpack('>H', result)[0]

    def write_ushort(self, addr, val):
        output_data = MAGIC_NUMBER + bytes((COMMAND_WRITE_UINT16, ))
        output_data += struct.pack('>Q', addr) + struct.pack('>H', val)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to write ushort: {error_message}')

        return return_code == 0

    def read_vector(self, addr):
        output_data = MAGIC_NUMBER + bytes((COMMAND_READ_VECTOR, ))
        output_data += struct.pack('>Q', addr)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to read vector: {error_message}')
            return None

        return Vector3(*struct.unpack('>fff', result))

    def write_vector(self, addr, v):
        output_data = MAGIC_NUMBER + bytes((COMMAND_WRITE_VECTOR, ))
        output_data += struct.pack('>Q', addr) + struct.pack('>fff', v.x, v.y, v.z)

        input_data = self.__send_data(output_data)
        return_code, result = self.__parse_received_data(input_data)

        if return_code != 0:
            error_message = result.decode('utf-8')
            print(f'Failed to write vector: {error_message}')

        return return_code == 0

    def __connect(self):
        if self.__socket is not None:
            return True

        port = None
        if os.path.isfile(port_temp_filepath):
            try:
                with open(port_temp_filepath, 'r', encoding='ascii') as f:
                    port = int(f.read())
            except (FileNotFoundError, TypeError, OverflowError, ValueError) as e:
                print(f'Unable to read port number from temp file ("{port_temp_filepath}"): '
                      f'{str(e)}')

        if port is not None:
            print(f'Connecting to {port}...')

            self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.__socket.connect((HOST, port))
                print('Connected.')
            except Exception as e:  # pylint: disable=broad-except
                self.__socket = None
                print(f'Failed to connect: {str(e)}')

        if self.__socket is None:
            script_path = os.path.realpath(__file__)
            print('Ensure that the Dolphin Hook server is running in a separate process with '
                  f'elevated permissions:\n\n   sudo python3 "{script_path}"')

        return self.__socket is not None

    def __send_data(self, output_data: bytes) -> bytes:
        try:
            self.__socket.sendall(output_data)
            return self.__socket.recv(MAX_DATA_LENGTH)
        except Exception as e:  # pylint: disable=broad-except
            print(f'Failed to send data: {str(e)}')
            return bytes()

    def __parse_received_data(self, data: bytes) -> tuple:
        if not data:
            return 1, b'Empty message'
        if not data.startswith(MAGIC_NUMBER):
            return 1, b'Bad magic number'

        return data[4], data[5:]


class Dolphin(DolphinClient):
    pass


if __name__ == '__main__':
    server = DolphinServer()
    server.run()
