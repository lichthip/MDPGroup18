from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_API_KEY")
project = rf.workspace("mdp-sho1t").project("mdp-merged")
version = project.version(1)
dataset = version.download("yolov8", "datasets/MDP-Merged-1")
