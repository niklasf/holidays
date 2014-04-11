del *.pyc
echo import holidays >> __compile__.py
echo import indexed >> __compile__.py
echo import message_queue >> __compile__.py
C:\Python27\python.exe __compile__.py
del __compile__.py
pause
