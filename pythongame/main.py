import os

game_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(game_directory)

game_path = os.path.join(game_directory, "game.exe.py")
with open(game_path, "r", encoding="utf-8") as game_file:
    exec(compile(game_file.read(), game_path, "exec"))
