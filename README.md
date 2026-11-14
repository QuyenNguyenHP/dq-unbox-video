# DQ Video: tự động dựng video unbox/review ngắn

Hệ thống dùng với [Claude Code](https://claude.com/claude-code) để làm video dọc 9:16 dài 50–60 giây (TikTok, Facebook Reels) review và unbox linh kiện điện tử, board nhúng, robot, đồ công nghệ.

Bạn chỉ cần **quay clip** (tay và sản phẩm) và **thu âm giọng một lần**. Claude sẽ:

1. Viết kịch bản kèm danh sách cảnh cần quay (tuỳ chọn).
2. Nhận dạng giọng nói, cắt đoạn ngập ngừng và câu đọc vấp.
3. Xem từng khung hình rồi ghép cảnh khớp với lời nói.
4. Thêm phụ đề tiếng Việt, chữ hook, nhãn tính năng bo tròn, logo, nhạc nền tự nhỏ lại khi có giọng.
5. Xuất MP4 1080×1920 vào `OUTPUT/` và Google Drive.

## Cài đặt (mỗi máy một lần)

Cần: Claude Code, git, kết nối mạng. Google Drive for desktop là tuỳ chọn.

**Windows** (kể cả laptop ARM như Snapdragon):
```powershell
git clone https://github.com/<tài-khoản>/dq-unbox-video.git
cd dq-unbox-video
powershell -ExecutionPolicy Bypass -File setup.ps1
```

**macOS / Linux:**
```bash
git clone https://github.com/<tài-khoản>/dq-unbox-video.git
cd dq-unbox-video
bash setup.sh
```

Script cài đặt sẽ cài ffmpeg và Python (nếu thiếu), tạo `.venv`, cài thư viện, tạo nhạc nền và kiểm tra máy. Cuối cùng phải thấy dòng **"Sẵn sàng!"**.

## Sử dụng

Mở thư mục này trong Claude Code rồi nhắn:

| Bạn nhắn | Claude làm |
|---|---|
| `viết kịch bản <sản phẩm> + vài thông tin` | Viết kịch bản ~55 giây và lưu vào `INPUT/<tên>/kichban.md` |
| `dựng video <tên>` | Dựng video từ thư mục `INPUT/<tên>/` |
| `đổi nhạc`, `đổi chữ hook thành …`, `đoạn X dùng cảnh khác` | Sửa và dựng lại trong 1–2 phút |

**Chuẩn bị file:** tạo thư mục `INPUT/<ten-video>/` (tên ngắn, không dấu), chép vào đó:
- tất cả clip (`.mp4`, `.mov`), ưu tiên quay dọc;
- **một** file thu âm giọng, nên đặt tên `voice.m4a`.

Nếu máy có Google Drive for desktop, bạn có thể tải file lên `My Drive/DQ Video/INPUT/<ten-video>/` từ điện thoại. Video xong sẽ tự xuất hiện ở `My Drive/DQ Video/OUTPUT/`.

## Tuỳ biến

- **Logo:** thay `assets/logo.png` (PNG nền trong suốt).
- **Màu thương hiệu:** `BRAND` trong `tools/render.py`.
- **Nhạc nền:** bỏ file `.mp3` không bản quyền vào `MUSIC/`.
- **Cấu hình riêng từng máy:** tạo `tools/config.local.json` để ghi đè `tools/config.json`, ví dụ:
  ```json
  { "ffmpeg": "D:/tools/ffmpeg/bin/ffmpeg.exe", "whisper_model": "medium", "drive_dir": "" }
  ```
  `whisper_model`: `small` (nhanh, mặc định) hoặc `medium` / `large-v3` (chính xác hơn, nên dùng khi máy có GPU hoặc CPU mạnh).

## Cấu trúc

```
.claude/skills/dq-unbox-video/SKILL.md   quy trình cho Claude (kịch bản + dựng)
tools/analyze.py      proxy clip, ảnh khung hình, nhận dạng giọng, cắt lặng
tools/render.py       dựng video từ _work/<tên>/edit.json
tools/make_music.py   tạo nhạc nền không bản quyền
tools/doctor.py       kiểm tra máy
assets/logo.png       logo gắn vào mọi video
INPUT/  OUTPUT/  _work/  MUSIC/   dữ liệu (không đưa lên git)
```

## Ghi chú

Logo DQ Tech trong `assets/` thuộc về DQ Tech; khi tự dùng, hãy thay bằng logo của bạn.
