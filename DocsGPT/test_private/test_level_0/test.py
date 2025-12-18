import torch

print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))

#######################################################

print("CUDA available:", torch.cuda.is_available())
print("CUDA device count:", torch.cuda.device_count())
print("CUDA device name:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
