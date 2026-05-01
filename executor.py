import os

def execute_command(command):
    print("\n[执行中...]")
    cmds = command.split("\n")
    for cmd in cmds:
        os.system(cmd)
