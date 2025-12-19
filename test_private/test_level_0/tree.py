import os

def print_tree(startpath, prefix=""):
    files = os.listdir(startpath)
    files.sort()
    for i, name in enumerate(files):
        path = os.path.join(startpath, name)
        connector = "└── " if i == len(files) - 1 else "├── "
        print(prefix + connector + name)
        if os.path.isdir(path):
            extension = "    " if i == len(files) - 1 else "│   "
            print_tree(path, prefix + extension)

# Gọi hàm với đường dẫn dự án
print_tree("D:\Github\KLTN")