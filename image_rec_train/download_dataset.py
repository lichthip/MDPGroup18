from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_API_KEY")
project = rf.workspace("mdp-sho1t").project("mdp-merged")
version = project.version(1)
dataset = version.download("yolov8", "datasets/MDP-Merged-1")
# You may need to update datasets/MDP-Merged-1/data.yaml with the correct paths after downloading:
# ```
# # ... other lines ...
# path: /absolute/path/to/datasets/MDP-Merged-1
# test: test/images
# train: train/images
# val: valid/images
# # ... other lines ...
