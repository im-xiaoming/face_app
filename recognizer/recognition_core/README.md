# Recognition Core

Folder nay quan ly rieng logic recognition.

Luồng hiện tại:

1. Frontend gửi frame camera lên `/recognition/api/` mỗi khoảng 1 giây.
2. Backend lưu frame tạm, detect/align face bằng `preprocess_face()`.
3. Check chất lượng bằng `estimate_pose_and_quality()`.
4. Ghi ảnh aligned tạm rồi trích embedding bằng `inference()`.
5. Search embedding trong Qdrant.
6. Gom kết quả theo `user_id`, cộng điểm nhẹ nếu match cùng pose hoặc nhiều pose của cùng user.
7. Trả `recognized` nếu score đủ cao và cách user thứ 2 đủ xa, ngược lại trả `unknown`.
8. Frontend chỉ hiện tên khi cùng một user được nhận diện ổn định trong vài frame liên tiếp.

Quy tắc số lượng khuôn mặt:

- Nếu không phát hiện khuôn mặt: reject frame.
- Nếu phát hiện nhiều hơn một khuôn mặt: reject frame và báo `Chi duoc co mot khuon mat trong anh.`
- Nếu đúng một khuôn mặt: tiếp tục align, trích embedding và search trong Qdrant.
