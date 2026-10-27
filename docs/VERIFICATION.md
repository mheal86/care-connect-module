# Kiểm tra bản đóng gói

Ngày xác nhận: 28/10/2026. Kiểm tra trực tiếp trên bản clone độc lập, môi trường Node.js 22 + Python 3.12 + PostgreSQL.

| Hạng mục kiểm tra | Kết quả ghi nhận |
|---|---|
| Backend unit & PostgreSQL integration | 23/23 ca đạt; gồm kiểm tra mật khẩu demo, phiên đăng nhập và phân quyền |
| Frontend unit tests | 28/28 ca đạt: store, màn hình đăng nhập, ánh xạ tên hồ sơ tiếng Việt |
| Angular production build | Thành công (`0 errors`) |
| Luồng API qua frontend proxy | Toàn bộ các endpoint hoạt động thông suốt |
| Chrome desktop & mobile | Kiểm tra giao diện ở 1366px, 1280px, 768px, 390px và 320px không bị lỗi tràn ngang hay che khuất nút thao tác |
| Hộp thoại danh mục & gợi ý | Các dropdown `p-select` hiển thị nền sắc nét, viền rõ ràng, căn chỉnh đúng trong khung nhìn |

### Các luồng nghiệp vụ đã xác minh:
- Đăng nhập và phân quyền trên 4 tài khoản mẫu (`family_demo`, `staff_demo`, `elder_demo`, `other_demo`).
- Tra cứu cơ sở, tìm kiếm không dấu, lọc theo khu vực, loại hình và dịch vụ chăm sóc.
- Tạo yêu cầu tư vấn, kiểm tra ràng buộc trường bắt buộc và xác nhận đồng ý chia sẻ thông tin.
- Cơ chế chống gửi lặp qua `Idempotency-Key` và khóa lạc quan chống xung đột phiên bản `expectedVersion`.
- Quy trình cơ sở xem xét, đề xuất đổi lịch hẹn và gia đình xác nhận lịch tư vấn.
- Tiện ích mở rộng: chia sẻ hồ sơ có thời hạn, gợi ý cơ sở theo tiêu chí có giải thích, và gửi đánh giá phản hồi sau tư vấn.

### Ghi chú kỹ thuật:
- Toàn bộ cảnh báo phụ thuộc CommonJS (Leaflet) và deprecation notice (Starlette TestClient) đã được ghi nhận và không ảnh hưởng đến quá trình build hay thực thi kiểm thử.
- CI GitHub Actions tự động thực thi lại toàn bộ test suite mỗi khi có commit mới lên nhánh `main`.
