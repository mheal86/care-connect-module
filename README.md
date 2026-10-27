# Care Connect Module

Module kết nối người cao tuổi với viện dưỡng lão và các trung tâm chăm sóc sức khỏe (sản phẩm thực hành bổ sung trong học kỳ thực tế của sinh viên Nguyễn Minh Hiếu).

Kho mã nguồn này chứa trọn vẹn mã nguồn của phân hệ Care Connect (Angular frontend, FastAPI backend và cơ sở dữ liệu PostgreSQL), được cấu hình để có thể cài đặt và chạy thử nghiệm độc lập trên máy cá nhân mà không phụ thuộc vào toàn bộ hệ thống lớn.

## Tính năng chính

- **Tra cứu & Tìm kiếm cơ sở**: Lọc danh sách theo khu vực, loại hình chăm sóc, dịch vụ và xem vị trí trên bản đồ tương tác.
- **Đặt lịch tư vấn**: Biểu mẫu 2 bước chọn dịch vụ, khung giờ phù hợp, nhập nhu cầu và xác nhận đồng ý chia sẻ thông tin.
- **Quy trình tiếp nhận & xử lý lịch**: Cơ sở xem xét yêu cầu, xác nhận hoặc đề xuất đổi lịch hẹn; gia đình phản hồi và xác nhận lịch tư vấn.
- **Quản lý danh mục cơ sở**: Phân quyền nhân viên/quản lý cơ sở cập nhật dịch vụ, giá tham khảo và trạng thái tiếp nhận.
- **Độ tin cậy & Toàn vẹn dữ liệu**: Cơ chế chống gửi lặp (Idempotency Key), khóa lạc quan (Optimistic Concurrency) chống ghi đè phiên bản và kiểm soát sức chứa khung giờ.
- **Tiện ích mở rộng**: Gợi ý cơ sở theo tiêu chí có giải thích, đánh giá phản hồi sau tư vấn, và chia sẻ hồ sơ sức khỏe có thời hạn.

## Công nghệ

Angular 21, TypeScript, PrimeNG, Leaflet; FastAPI, Python 3.12; PostgreSQL. Không cần khóa OpenAI, mô hình giọng nói hay dịch vụ AI bên ngoài để chạy module này.

## Chạy tại máy

Cần Node.js 22, Python 3.12, uv và Docker Compose (hoặc PostgreSQL riêng).

1. Sao chép `.env.example` thành `.env` ở thư mục gốc. Đặt `DEMO_PASSWORD` riêng dài ít nhất 12 ký tự. Các giá trị database ví dụ chỉ dành cho database demo mới được tạo bởi Compose.
2. Từ thư mục gốc, chạy:

```sh
docker compose up -d db
uv sync --extra dev
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8008
```

3. Mở terminal khác:

```sh
cd frontend
npm ci
npm start
```

4. Truy cập giao diện tại `http://127.0.0.1:4208/care-connect`.
- **Các tài khoản mẫu**:
  - `family_demo`: Vai trò gia đình (tìm kiếm cơ sở, gửi và theo dõi yêu cầu tư vấn).
  - `staff_demo`: Vai trò nhân viên & quản lý cơ sở (tiếp nhận yêu cầu, xếp lịch hẹn, chỉnh sửa danh mục).
  - `elder_demo`: Tài khoản người cao tuổi mẫu.
  - `other_demo`: Tài khoản gia đình khác (dùng để kiểm tra phân quyền và cách ly dữ liệu).
- **Mật khẩu đăng nhập**: Nhập mật khẩu bạn đã thiết lập trong biến `DEMO_PASSWORD` tại file `.env` (mặc định tại máy khi bàn giao: `CareConnectLocal-2026`).

Tài liệu Swagger / OpenAPI backend: `http://127.0.0.1:8008/docs`. Giao diện gọi API qua proxy cùng nguồn để duy trì cookie phiên.

## Kiểm thử

```sh
# Từ thư mục gốc: nhóm unit không cần PostgreSQL; nhóm postgres tự bỏ qua khi chưa cấu hình.
uv run pytest -q

# Chạy đủ nhóm PostgreSQL trên database care_connect_test do Compose tạo.
# Linux/macOS:
export TEST_DATABASE_URL='postgresql://care_demo:local-demo-db-only@127.0.0.1:5548/care_connect_test'
# PowerShell:
# $env:TEST_DATABASE_URL = 'postgresql://care_demo:local-demo-db-only@127.0.0.1:5548/care_connect_test'
uv run pytest -q

cd frontend
npm test
npm run build
```

Nhóm PostgreSQL xóa dữ liệu trong database kiểm thử. Chỉ sử dụng database riêng có tên kết thúc bằng `_test` hoặc `test`; không đặt địa chỉ database demo/ứng dụng vào `TEST_DATABASE_URL`. Kết quả thực tế của bản đóng gói được ghi ở [docs/VERIFICATION.md](docs/VERIFICATION.md); CI chạy lại cả hai phía.

## Đọc mã nguồn

| Đường dẫn | Nội dung |
|---|---|
| `frontend/src/app/features/care-connect/` | Màn hình, trạng thái, quy tắc, bản đồ và kiểm thử store |
| `frontend/src/app/core/api/care-connect.service.ts` | Hợp đồng dữ liệu và lớp gọi HTTP |
| `backend/routes/care_connect.py` | API cơ sở, yêu cầu, lịch và phản hồi |
| `backend/routes/care_extensions.py` | Hỗ trợ thử nghiệm và chia sẻ hồ sơ |
| `backend/core/features/care_connect/` | Mô hình trạng thái, kiểm tra dữ liệu, gợi ý và PostgreSQL store |
| `backend/core/db/schema.py` | Bảng của module và các bảng hợp đồng tối thiểu cho demo |
| `backend/tests/` | Unit test và PostgreSQL integration test |
| `docs/schema.sql` | Lược đồ SQL có thể đọc trực tiếp |

Xem thêm [kiến trúc và phạm vi tách](docs/ARCHITECTURE.md), [kịch bản trình diễn](docs/DEMO.md), [phạm vi công khai](docs/PUBLIC_SCOPE.md).

## Ghi chú về dữ liệu & phạm vi
- Dữ liệu cơ sở, khung giờ và hồ sơ trong repo là dữ liệu mẫu phục vụ kiểm thử và demo chức năng.
- Thuật toán gợi ý cơ sở dựa trên hệ luật tham khảo, mang tính định hướng thông tin và không thay thế tư vấn y khoa chuyên môn.
- Tính năng gửi cảnh báo thử nghiệm trong phần tiện ích mở rộng là luồng mô phỏng sự kiện trong ứng dụng, chưa kết nối với tổng đài cấp cứu hay thiết bị IoT thực tế.
