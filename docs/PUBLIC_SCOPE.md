# Phạm vi kho mã nguồn

Kho lưu trữ này được xây dựng nhằm phục vụ việc nghiệm thu, kiểm thử và báo cáo học tập cho đề tài **Care Connect Module** của sinh viên Nguyễn Minh Hiếu.

### Thành phần bao gồm:
- Toàn bộ mã nguồn giao diện module Care Connect (Angular 21 standalone, Signals, PrimeNG).
- Máy chủ API xử lý nghiệp vụ (FastAPI, Python 3.12, PostgreSQL).
- Lược đồ cơ sở dữ liệu và dữ liệu seed mẫu phục vụ chạy thử cục bộ.
- Bộ kiểm thử tự động (Unit test, Integration test) và cấu hình CI GitHub Actions.

### Phạm vi bảo mật & quy định:
- Dự án không chứa bất kỳ khóa bí mật, cấu hình môi trường thực tế (`.env`), cookie phiên làm việc hay dữ liệu người dùng thật.
- Các phân hệ nội bộ khác của doanh nghiệp và lịch sử mã nguồn dự án gốc được loại trừ hoàn toàn nhằm tuân thủ quy định bảo mật thông tin.
- Toàn bộ thông tin cá nhân, số điện thoại, địa chỉ và cơ sở chăm sóc hiển thị trong ứng dụng đều là dữ liệu giả lập phục vụ mục đích kiểm thử phần mềm.
