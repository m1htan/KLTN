from pathlib import Path

# ====== THU MUC CHUA FILE ======
TARGET_DIR = Path(r"D:\Github\KLTN\application\inputs\full_law")
# ===============================

# Danh sach ten file can xoa (KHONG can duoi file)
TARGET_NAMES = {
    "Luật-01-2011-QH13",
    "Luật-11-2012-QH13",
    "Luật-11-2022-QH15",
    "Luật-12-2012-QH13",
    "Luật-13-2008-QH12",
    "Luật-14-2017-QH14",
    "Luật-17-2012-QH13",
    "Luật-17-2017-QH14",
    "Luật-22-2008-QH12",
    "Luật-23-2008-QH12",
    "Luật-23-2012-QH13",
    "Luật-24-2012-QH13",
    "Luật-25-2012-QH13",
    "Luật-27-2001-QH10",
    "Luật-28-2001-QH10",
    "Luật-28-2004-QH11",
    "Luật-28-2018-QH14",
    "Luật-30-2009-QH12",
    "Luật-31-2013-QH13",
    "Luật-32-2009-QH12",
    "Luật-39-2019-QH14",
    "Luật-40-2013-QH13",
    "Luật-41-2009-QH12",
    "Luật-45-2013-QH13",
    "Luật-47-2010-QH12",
    "Luật-47-2019-QH14",
    "Luật-50-2019-QH14",
    "Luật-51-2005-QH11",
    "Luật-53-2014-QH13",
    "Luật-58-2014-QH13",
    "Luật-59-2010-QH12",
    "Luật-59-2014-QH13",
    "Luật-60-2010-QH12",
    "Luật-62-2014-QH13",
    "Luật-63-2020-QH14",
    "Luật-65-2014-QH13",
    "Luật-66-2011-QH12_",
    "Luật-66-2014-QH13",
    "Luật-69-2014-QH13",
    "Luật-76-2015-QH13",
    "Luật-77-2015-QH13",
    "Luật-80-2015-QH13",
    "Luật-87-2015-QH13",
}

deleted = []

for p in TARGET_DIR.iterdir():
    if not p.is_file():
        continue

    stem = p.stem  # ten file khong co duoi .pdf/.docx/...
    if stem in TARGET_NAMES:
        p.unlink()
        deleted.append(p.name)

print(f"Da xoa {len(deleted)} file:")
for f in deleted:
    print(" -", f)
