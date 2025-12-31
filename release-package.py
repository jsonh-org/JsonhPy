import subprocess

subprocess.call("py -m twine upload --repository pypi dist/*", shell = True)