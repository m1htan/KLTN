# Tóm tắt thông tin từ DocsGPT

## Tổng quan
- DocsGPT là nền tảng AI mã nguồn mở giúp xây dựng agent và trợ lý thông minh, hỗ trợ phân tích tài liệu (PDF, Office, web) với nhiều mô hình và API, có thể triển khai ở bất cứ đâu với quyền riêng tư kiểm soát được.【F:README.md†L9-L45】
- Trang chủ tài liệu (docs.docsgpt.cloud) mô tả DocsGPT như một công cụ genAI mã nguồn mở giúp trả lời đáng tin cậy từ mọi nguồn tri thức và tích hợp sẵn khả năng agent/tooling.【F:docs/pages/index.mdx†L60-L83】

## Tính năng chính
- Hỗ trợ nhiều định dạng: PDF, DOCX, CSV, XLSX, EPUB, MD, RST, HTML, MDX, JSON, PPTX, và hình ảnh.【F:README.md†L37-L46】
- Nguồn dữ liệu web: nhập từ URL, sitemap, Reddit, GitHub, crawler.【F:README.md†L37-L46】
- Câu trả lời kèm trích dẫn để hạn chế hallucination.【F:README.md†L37-L46】
- Quản lý API key gắn với cấu hình và tài liệu, dễ thiết lập chatbot/tích hợp.【F:README.md†L37-L46】
- Hành động qua công cụ/API, nhiều tích hợp sẵn (widget HTML/React, bot Discord/Telegram, công cụ tìm kiếm).【F:README.md†L37-L46】
- Hỗ trợ mô hình đám mây (OpenAI, Google, Anthropic…) và mô hình cục bộ (Ollama, llama_cpp).【F:README.md†L37-L46】
- Triển khai bảo mật, hỗ trợ Kubernetes cho quy mô doanh nghiệp.【F:README.md†L37-L46】

## Lộ trình (Roadmap)
- Đã hoàn thành: tương thích GoogleAI, hệ thống tools, ReACT agent, tối ưu agent, cập nhật nguồn filesystem, phản hồi JSON, hỗ trợ MCP, Google Drive, OAuth 2.0 cho MCP (đến tháng 9/2025).【F:README.md†L50-L64】
- Kế hoạch: tích hợp SharePoint, Deep Agents, và lập lịch agent từ tháng 10/2025 trở đi.【F:README.md†L64-L66】

## Hướng dẫn khởi chạy nhanh (Quickstart)
- Yêu cầu Docker trước khi bắt đầu.【F:README.md†L84-L88】【F:docs/pages/quickstart.mdx†L8-L15】
- Bước cơ bản (macOS/Linux):
  1. Clone repo `arc53/DocsGPT` và chuyển vào thư mục dự án.【F:README.md†L91-L97】【F:docs/pages/quickstart.mdx†L18-L25】
  2. Chạy script `./setup.sh` để được cấu hình tương tác.【F:README.md†L100-L105】【F:docs/pages/quickstart.mdx†L27-L62】
  3. Chọn một trong 5 chế độ: dùng Public API, chạy local với Ollama, kết nối engine suy luận cục bộ (Llama.cpp/TGI/vLLM…), kết nối nhà cung cấp API đám mây (OpenAI/Google/Anthropic/Groq/HuggingFace/Azure), hoặc tự build image từ mã nguồn.【F:docs/pages/quickstart.mdx†L37-L62】【F:README.md†L114-L116】
  4. Truy cập giao diện tại `http://localhost:5173/` khi container đã chạy.【F:README.md†L116-L118】【F:docs/pages/quickstart.mdx†L64-L67】
  5. Dừng dịch vụ bằng `docker compose -f deployment/docker-compose.yaml down` (hoặc lệnh được script gợi ý).【F:README.md†L118-L125】【F:docs/pages/quickstart.mdx†L68-L75】
- Windows: chạy `PowerShell -ExecutionPolicy Bypass -File .\setup.ps1` rồi làm theo hướng dẫn tương tự; đảm bảo Docker Desktop đang chạy.【F:README.md†L106-L114】【F:docs/pages/quickstart.mdx†L77-L114】

## Tài nguyên liên quan
- Roadmap đầy đủ: https://github.com/orgs/arc53/projects/2.【F:README.md†L48-L68】
- Hướng dẫn cấu hình nâng cao: tài liệu DocsGPT Settings và triển khai Docker/development nằm trên docs.docsgpt.cloud.【F:README.md†L126-L127】【F:docs/pages/index.mdx†L20-L58】
- Kênh hỗ trợ & cộng đồng: Discord, blog, form demo, email support, và chương trình Lighthouse dành cho đội kỹ thuật triển khai thực tế.【F:README.md†L22-L83】

