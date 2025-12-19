from pathlib import Path
from application.parser.file.docs_parser import DocxParser

parser = DocxParser()
file = Path("/application/inputs/local/Bộ luật-45-2019-QH14.docx")

text = parser.parse_file(file)

# chọn 1 điều có đủ: nhiều khoản + điểm + kéo dài dòng
start = text.find("Điều 3.")
print(text[start:start + 3000])
