## evaluate/

Thư mục này dùng để chạy bộ kiểm thử chất lượng (evaluation) cho chatbot luật Việt Nam, ưu tiên nhóm luật kinh tế / doanh nghiệp và các tình huống người dùng "không rành luật".

### Mục tiêu
- Đo khả năng: 
  - (1) định hướng đúng luật liên quan 
  - (2) trả lời có căn cứ (Điều/Khoản) 
  - (3) biết hỏi lại khi thiếu dữ kiện 
  - (4) không bịa điều khoản / không phán bừa.
- Bao phủ tình huống thực tế: người dùng hỏi vu vơ, hỏi không có ngữ cảnh, hỏi theo ngôn ngữ kinh doanh/công nghệ.

### Cấu trúc
- golden_sets/: dữ liệu golden set (YAML)
- prompts/: rubric + guardrails để thống nhất cách chấm
- runners/: code load + chạy + chấm điểm
- tests/: unit tests cho loader + scoring

### Chạy nhanh
```bash
python -m evaluate.runners.run_eval --golden evaluate/golden_sets/vn_business_core.yaml
python -m evaluate.runners.run_eval --golden evaluate/golden_sets/vn_business_edge.yaml
python -m evaluate.runners.run_eval --golden evaluate/golden_sets/vn_business_stress.yaml
```

### Tích hợp vào hệ thống của bạn
- Runner này hỗ trợ 2 chế độ:
  1) Gọi HTTP endpoint (mặc định): bạn trỏ tới API trả lời của chatbot.
  2) Gọi shell command: nếu bạn có CLI nội bộ.

Xem `evaluate/runners/run_eval.py` để cấu hình.

