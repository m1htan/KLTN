import os

# Thư mục / file cần loại bỏ
EXCLUDE_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".env",
    ".env.local",
    ".DS_Store"
}

# Chỉ lấy file source chính
ALLOWED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".java"}


def is_valid(path: str) -> bool:
    name = os.path.basename(path)

    # Bỏ file/thư mục ẩn & config
    if name.startswith(".") or name in EXCLUDE_NAMES:
        return False

    # Nếu là file → kiểm tra extension
    if os.path.isfile(path):
        return os.path.splitext(name)[1] in ALLOWED_EXTENSIONS

    # Nếu là thư mục → cho phép duyệt tiếp
    return True


def print_tree(startpath, prefix=""):
    try:
        entries = [
            os.path.join(startpath, name)
            for name in os.listdir(startpath)
            if is_valid(os.path.join(startpath, name))
        ]
    except PermissionError:
        return

    entries.sort(key=lambda x: os.path.basename(x))

    for i, path in enumerate(entries):
        name = os.path.basename(path)
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(prefix + connector + name)

        if os.path.isdir(path):
            extension = "    " if i == len(entries) - 1 else "│   "
            print_tree(path, prefix + extension)


# Gọi hàm
print_tree(r"D:\Github\KLTN")
