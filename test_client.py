# client

import socket
import json
import time
address = ('10.201.16.165', 6666)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(address)

# payload = {"type": "wind", "windtemp": 20, "velocity": "NONE"}
payload = {"type": "temp", "temp": 20}
print('send_temp')
s.send(json.dumps(payload).encode('utf-8'))
# my_writer_obj = s.makefile(mode='w')
# my_writer_obj.write(json.dumps(payload))
# my_writer_obj.flush()

# s.send(('hihi').encode('utf-8'))
buffer_data = s.recv(1024)
buffer_data = json.loads(buffer_data.decode('utf-8'))
print('the data received is: ', buffer_data)

if buffer_data['type'] == 'freshrate':
    print('send_auth')
    payload = {"type": "auth", "room": "A15", "ID": "123456789012344567"}
    s.send(json.dumps(payload).encode('utf-8'))
    # my_writer_obj = s.makefile(mode='w')
    #
    # my_writer_obj.write(json.dumps(payload))
    # my_writer_obj.flush()

buffer_data = s.recv(1024)
buffer_data = json.loads(buffer_data.decode('utf-8'))
print('the data received is: ', buffer_data)


if buffer_data['type'] == 'mode':
    print('send_startwind')
    payload = {"type": "startwind",
               "desttemp": 25,
               "velocity": 'HIGH'}
    s.send(json.dumps(payload).encode('utf-8'))
    # my_writer_obj = s.makefile(mode='w')
    #
    # my_writer_obj.write(json.dumps(payload))
    # my_writer_obj.flush()

buffer_data = s.recv(1024)
buffer_data = json.loads(buffer_data.decode('utf-8'))
print('the data received is: ', buffer_data)



if buffer_data['type'] == 'wind':
    time.sleep(10)
    print('send_stopwind')
    payload = {"type": "stopwind"}
    s.send(json.dumps(payload).encode('utf-8'))
    # my_writer_obj = s.makefile(mode='w')
    #
    # my_writer_obj.write(json.dumps(payload))
    # my_writer_obj.flush()

buffer_data = s.recv(1024)
buffer_data = json.loads(buffer_data.decode('utf-8'))
print('the data received is: ', buffer_data)
