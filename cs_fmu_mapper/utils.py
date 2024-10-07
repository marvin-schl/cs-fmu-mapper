import inquirer
import os


def chooseFile(path, message):
    if not os.path.exists(path):
        raise FileNotFoundError("Path does not exist: " + path)

    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    questions = [inquirer.List("file", message=message, choices=files)]
    answers = inquirer.prompt(questions)
    return answers["file"]
