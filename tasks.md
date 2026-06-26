# Kế hoạch sửa & refactor Frontend (IoT Management Console)

> **Mục tiêu:** Sửa lỗi chất lượng (i18n mất dấu, bug logic trạng thái) + refactor toàn diện để dùng design system, tách component dùng chung, cải thiện accessibility.
>
> **Stack:** React 19 + Vite + Tailwind v4 + shadcn/ui (Radix) + react-router-dom v6. Thư mục FE: `app_service/`.
>
> **Cách chạy/kiểm thử trong lúc dev:**
> - Production stack đang chạy qua Docker: frontend `http://localhost:80`, backend `http://localhost:8001`.
> - Tài khoản admin để test: `AD00000` / `khanhxx007`.
> - Dev server (hot reload): `cd app_service && npm run dev` → `http://localhost:3000` (LƯU Ý: dev mode KHÔNG có proxy/.env nên API trỏ về cùng origin → 404. Để test API thật trong dev, tạo `.env` với `VITE_API_URL=http://localhost:8001` và `VITE_WS_URL=ws://localhost:8001` — xem Task 0).
> - Build kiểm tra lỗi: `cd app_service && npm run build`.
> - Sau mỗi task: `npm run build` phải PASS (không cần test runner — repo chưa có test).

---

## ⚠️ Bối cảnh kỹ thuật bắt buộc đọc trước khi code

1. **Backend trả `status` = `"active"` / `"deactive"`**, KHÔNG phải `"online"`/`"offline"`.
   - Các trang FE đang so sánh `device.status === 'online'` → luôn sai → mọi thiết bị hiển thị như offline (chấm đỏ + nút "Turn On").
   - File ảnh hưởng: `src/pages/Devices.jsx`, `src/pages/DeviceDetail.jsx`, `src/pages/Home.jsx`.
   - `device_id` từ API là **số nguyên** (1, 2, 3), không phải chuỗi "DEV001".

2. **Token shadcn hiện tại KHÔNG khớp theme thực tế.** Trong `generated/webflow.css`:
   - `--card-dark: #191919` (xám đen), `--primary: #1a1b1f` (gần như đen), `--background: #f5f7fa` (TRẮNG — light).
   - App thực tế đang là **dark slate** (`bg-slate-900` = `#0f172a`) + **primary blue** (`bg-blue-600`).
   - ⛔ **KHÔNG** được thay máy móc `bg-slate-800` → `bg-card`, vì token sẽ ra màu sai (card thành #191919, primary thành đen).
   - ✅ Phải **định nghĩa lại bộ token cho khớp theme slate/blue hiện tại TRƯỚC** (Task 5), rồi mới refactor sang token (Task 6+).

3. **Backend KHÔNG có endpoint `/api/alerts` hoặc `/api/dashboard/summary`.** Trang Home đang dùng 100% mock (`src/data/mockData.js`). → Quyết định: **giữ mock tạm thời**, chỉ đánh dấu rõ là demo data (Task 4). Không bịa endpoint.

4. **Endpoint backend hiện có** (để tham chiếu, không tự bịa):
   `GET /api/devices`, `/api/devices/my`, `/api/devices/topics`, `/api/devices/{id}`, `PATCH /api/devices/{id}`, `DELETE /api/devices/{id}`, `PUT /api/devices/{id}/topic`, `GET /api/users`, `PATCH/DELETE /api/users/{id}`, `GET/POST /api/authorizations`, `GET /api/mqtt/messages`, `/api/mqtt/history`, `/api/mqtt/topics`, `/api/mqtt/status`, `GET /api/locations`, `GET /api/health`.

5. **Quy ước i18n:** UI dùng tiếng Việt CÓ DẤU đầy đủ. Một số file đang viết KHÔNG DẤU (Dashboard, TopicManagement) — phải sửa lại có dấu. KHÔNG dùng hàm `foldText`/bỏ dấu cho text hiển thị (chỉ dùng để so khớp/normalize logic nếu cần).

---

## Kiến trúc / quyết định đã chốt

- **Home:** giữ mock, chỉ thêm nhãn "Dữ liệu demo".
- **Design system:** tạo lớp component dùng chung (`PageHeader`, `StatCard`, `Panel`, `StatusBadge`) dùng token; refactor dần từng trang.
- **Phạm vi:** sửa lỗi + refactor toàn diện (nhiều phase).
- **Modal tự chế** (xóa device, ChangePasswordModal) → thay bằng `<Dialog>`/`<AlertDialog>` của shadcn (đã cài sẵn ở `src/components/ui/`).
- **Nút "Turn On/Off"** ở DeviceCard hiện chỉ đổi state local (không gọi API) → gây hiểu nhầm điều khiển được thiết bị. Quyết định ở Task 3.

---

# Phase 0 — Chuẩn bị môi trường

## Task 0: Tạo file `.env` cho dev + tài liệu hoá
**Mô tả:** Hiện dev server (`npm run dev`) không gọi được API vì thiếu cấu hình base URL. Tạo `.env` (gitignored) để dev gọi backend Docker, và `.env.example` để người sau biết.

**Cần làm:**
- Tạo `app_service/.env.example` với nội dung:
  ```
  VITE_API_URL=http://localhost:8001
  VITE_WS_URL=ws://localhost:8001
  ```
- Tạo `app_service/.env` cùng nội dung (file thật để dev dùng).
- Kiểm tra `.gitignore` đã ignore `.env` (thêm dòng `.env` nếu chưa, nhưng GIỮ `.env.example`).

**Acceptance criteria:**
- [ ] `npm run dev` → mở `http://localhost:3000` → đăng nhập `AD00000`/`khanhxx007` thành công (request đi tới `:8001`).
- [ ] `.env` không bị commit; `.env.example` được commit.

**Verification:**
- [ ] `npm run dev`, đăng nhập thành công, vào `/devices` thấy 3 device thật.
- [ ] `git status` không thấy `.env` trong danh sách track.

**Dependencies:** None
**Files likely touched:** `app_service/.env`, `app_service/.env.example`, `app_service/.gitignore`
**Estimated scope:** XS

---

# Phase 1 — Sửa lỗi nghiêm trọng (critical)

## Task 1: Sửa i18n mất dấu tiếng Việt
**Mô tả:** Trang Dashboard và Topic Management hiển thị text tiếng Việt KHÔNG DẤU, lệch hẳn so với các trang khác. Sửa lại có dấu đầy đủ.

**Cần làm — sửa CHÍNH XÁC các chuỗi sau (giữ nguyên ý, chỉ thêm dấu):**

Trong `src/pages/GlobalDashboard.jsx`:
- `'Tong quan tat ca thiet bi (admin)'` → `'Tổng quan tất cả thiết bị (admin)'`
- `'Tong quan thiet bi duoc phan quyen (user)'` → `'Tổng quan thiết bị được phân quyền (user)'`
- `'Truc X: thiet bi - Truc Y: gia tri'` → `'Trục X: thiết bị · Trục Y: giá trị'` (cả 4 chỗ `subtitle`)
- `'Khong tai duoc danh sach thiet bi'` → `'Không tải được danh sách thiết bị'`
- `'Dang tai danh sach thiet bi...'` → `'Đang tải danh sách thiết bị...'`
- Tooltip nút phóng to: `'Thu nho bieu do'` → `'Thu nhỏ biểu đồ'`, `'Phong to bieu do'` → `'Phóng to biểu đồ'`
- Cảnh báo `'Missing VITE_WS_URL. Dashboard chua nhan realtime.'` → `'Thiếu VITE_WS_URL. Dashboard chưa nhận dữ liệu realtime.'`

Trong `src/pages/TopicManagement.jsx`:
- `'Quan ly topic MQTT'` → `'Quản lý topic MQTT'`
- `'Admin luu topic tren bang device va backend se auto subscribe.'` → `'Admin lưu topic trên bảng device và backend sẽ tự động subscribe.'`
- `'Lam moi'` → `'Làm mới'`
- `'Topic runtime dang subscribe'` → `'Topic runtime đang subscribe'`
- `'Chua co topic nao.'` → `'Chưa có topic nào.'`
- `'Gan topic nhan/topic gui theo tung thiet bi (bo trong de xoa gia tri).'` → `'Gán topic nhận/topic gửi theo từng thiết bị (bỏ trống để xoá giá trị).'`
- Cột: `'Ten thiet bi'` → `'Tên thiết bị'`, `'Trang thai'` → `'Trạng thái'`
- `'Khong tai duoc du lieu topic'` → `'Không tải được dữ liệu topic'`
- `'Da luu topic nhan/gui cho device ${deviceId}'` → `'Đã lưu topic nhận/gửi cho device ${deviceId}'`
- `'Luu topic that bai'` → `'Lưu topic thất bại'`
- `'Dang tai...'` → `'Đang tải...'`
- Nút: `'Dang luu...'` → `'Đang lưu...'`, `'Luu'` → `'Lưu'`

**Acceptance criteria:**
- [ ] Không còn chuỗi tiếng Việt không dấu nào trong 2 file (kiểm tra mục tiêu phía dưới).
- [ ] Ý nghĩa giữ nguyên, không đổi logic.

**Verification:**
- [ ] `npm run build` PASS.
- [ ] Mở `/dashboard` và `/topic-management` trên browser → mọi nhãn có dấu đúng.
- [ ] Grep còn sót: `grep -nE "\b(thiet bi|trang thai|quan ly|lam moi|dang tai|gia tri|du lieu|phan quyen)\b" src/pages/GlobalDashboard.jsx src/pages/TopicManagement.jsx` → không ra kết quả nào.

**Dependencies:** None
**Files likely touched:** `src/pages/GlobalDashboard.jsx`, `src/pages/TopicManagement.jsx`
**Estimated scope:** S

---

## Task 2: Sửa bug map trạng thái `active`/`deactive` → `online`/`offline`
**Mô tả:** Backend trả `status: "active"` nhưng FE so sánh `=== 'online'`. Hệ quả: mọi thiết bị hiển thị chấm đỏ + nút "Turn On" dù đang active. Tạo một helper map chuẩn và dùng ở tất cả nơi.

**Cần làm:**
- Tạo helper trong `src/lib/deviceStatus.js` (file mới):
  ```js
  /** Map status từ backend (active/deactive) HOẶC mock (online/offline) về dạng UI thống nhất. */
  export function toUiStatus(raw) {
    const s = String(raw ?? '').trim().toLowerCase();
    if (s === 'active' || s === 'online') return 'online';
    return 'offline';
  }
  export function isOnline(raw) {
    return toUiStatus(raw) === 'online';
  }
  ```
- Trong `src/pages/Devices.jsx`:
  - Trong `normalizedDevices` (useMemo), thêm field chuẩn hoá: gán `status: toUiStatus(d.status)` SAU khi spread `...d` để ghi đè (lưu ý: hiện code không normalize status — phải thêm).
  - `DeviceCard` đang dùng `device.status === 'online'` ở: icon bg, dot, label, nút toggle → giữ nguyên so sánh `=== 'online'` VÌ status đã được normalize trước khi truyền vào card. (Chỉ cần đảm bảo `normalizedDevices` đã map.)
  - Kiểm tra cả nhánh WebSocket `onmessage`: payload realtime có thể trả `status` khác → khi merge `{...d, ...data}` rồi đi qua `normalizedDevices` sẽ tự chuẩn hoá, OK.
- Trong `src/pages/DeviceDetail.jsx`: hàm `mapApiDeviceToUi` đã có `online = status === 'active'` → ĐÚNG rồi, nhưng kiểm tra mọi nơi hiển thị status trong file có nhất quán dùng biến `online` không (đừng so sánh chuỗi 'online' rời rạc). Thay các so sánh trực tiếp bằng `isOnline()` nếu có.
- Trong `src/pages/Home.jsx`: KPI dùng `deviceStatsSummary` từ mock (mock dùng 'online'/'offline') → helper `toUiStatus` vẫn map đúng, không cần đổi mock. (Home xử lý ở Task 4.)

**Acceptance criteria:**
- [ ] Thiết bị có `status: "active"` từ API hiển thị **chấm xanh + "ONLINE" + nút "Turn Off"**.
- [ ] Thiết bị `deactive` hiển thị **chấm đỏ + "OFFLINE" + nút "Turn On"**.
- [ ] Không còn so sánh `=== 'online'` với dữ liệu CHƯA normalize.

**Verification:**
- [ ] `npm run build` PASS.
- [ ] Trên `/devices` (3 device active): cả 3 hiện chấm xanh + "Turn Off".
- [ ] Vào `/devices/1` → trạng thái hiển thị "Online".
- [ ] Grep: `grep -rn "'online'\|'offline'" src/pages/Devices.jsx src/pages/DeviceDetail.jsx` → mọi chỗ đều thao tác trên status đã normalize.

**Dependencies:** None (nhưng nên làm sau Task 0 để test live)
**Files likely touched:** `src/lib/deviceStatus.js` (mới), `src/pages/Devices.jsx`, `src/pages/DeviceDetail.jsx`
**Estimated scope:** M

---

## Task 3: Xử lý nút "Turn On/Off" giả (chỉ đổi state local)
**Mô tả:** Nút toggle ở DeviceCard chỉ đổi state React (`handleToggleStatus`), KHÔNG gọi API → reload là mất, gây hiểu nhầm là điều khiển được thiết bị. Backend có `PATCH /api/devices/{id}` (đổi field device) nhưng KHÔNG có lệnh điều khiển bật/tắt thiết bị thật qua MQTT downlink ở REST.

**Quyết định (chọn 1 — coder hỏi nếu chưa rõ, mặc định phương án A):**
- **Phương án A (mặc định, an toàn):** Ẩn/bỏ nút "Turn On/Off" khỏi DeviceCard vì FE chưa có khả năng điều khiển thật. Thay bằng chỉ hiển thị badge trạng thái (read-only). Gỡ `handleToggleStatus` và prop `onToggle`.
- **Phương án B:** Giữ nút nhưng đổi nhãn thành rõ ràng (vd "Đánh dấu Online/Offline") và gọi `PATCH /api/devices/{id}` với `{ status: 'active'|'deactive' }`, optimistic update + rollback khi lỗi. CHỈ làm nếu PATCH chấp nhận field `status` (kiểm tra schema backend trước: đọc `app_service/backend/app/api/` route devices PATCH).

**Cần làm (phương án A):**
- Trong `src/pages/Devices.jsx`: bỏ `handleToggleStatus`, bỏ prop `onToggle` khi render `DeviceCard`.
- Trong `DeviceCard`: bỏ phần `<Button onClick={() => onToggle(...)}>Turn On/Off</Button>` ở footer; footer chỉ còn dot + label trạng thái.

**Acceptance criteria:**
- [ ] DeviceCard không còn nút có hành vi giả (không gọi API).
- [ ] Nếu chọn B: bấm nút → gọi PATCH thật, reload trang trạng thái vẫn đúng.

**Verification:**
- [ ] `npm run build` PASS.
- [ ] (A) Footer card chỉ còn badge trạng thái; không có nút toggle.
- [ ] (B) Bấm toggle → Network tab thấy `PATCH /api/devices/{id}` 200 → reload giữ trạng thái.

**Dependencies:** Task 2 (status đã normalize)
**Files likely touched:** `src/pages/Devices.jsx`
**Estimated scope:** S

---

## Task 4: Đánh dấu rõ dữ liệu demo ở trang Home
**Mô tả:** Home dùng 100% mock (`mockData.js`). Backend chưa có alerts/summary. Giữ mock nhưng phải nói rõ cho người dùng đây là dữ liệu demo, tránh hiểu nhầm là số liệu thật.

**Cần làm:**
- Trong `src/pages/Home.jsx`: thêm một banner nhỏ ngay dưới header:
  ```jsx
  <div className="p-3 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-200 text-sm">
    Dữ liệu trên trang này là <strong>demo</strong> (chưa kết nối API thật).
  </div>
  ```
- KHÔNG xoá mock, KHÔNG bịa endpoint.
- (Tuỳ chọn, không bắt buộc) đổi tiêu đề phụ cho rõ: giữ nguyên là được.

**Acceptance criteria:**
- [ ] Trang Home hiển thị banner cảnh báo "dữ liệu demo".
- [ ] Không thay đổi nguồn dữ liệu (vẫn từ mockData).

**Verification:**
- [ ] `npm run build` PASS.
- [ ] Mở `/home` → thấy banner amber.

**Dependencies:** None
**Files likely touched:** `src/pages/Home.jsx`
**Estimated scope:** XS

---

## Task 4b (phát sinh): Fix nginx cache cho index.html
**Mô tả:** Khi verify phát hiện nginx production KHÔNG set cache header cho `index.html` → trình duyệt cache bản cũ, user không nhận bản deploy mới cho tới khi hard-refresh. Đây là lỗi production thật.
**Đã làm:** Trong `nginx/prod.conf` và `nginx/prod.https.conf`:
- `location /assets/`: `Cache-Control: public, immutable` + `expires 1y` (file có hash an toàn cache dài).
- `location = /index.html`: `Cache-Control: no-cache, no-store, must-revalidate` + `expires -1`.
**Verify:** `curl -sI http://localhost/` → `Cache-Control: no-cache...`; `curl -sI http://localhost/assets/<hash>.js` → `immutable`. ✅ Đã verify.
**Files:** `nginx/prod.conf`, `nginx/prod.https.conf`

### ✅ Checkpoint A — sau Task 0–4
- [ ] `npm run build` PASS, không lỗi console khi chạy app.
- [ ] `/dashboard` và `/topic-management` tiếng Việt có dấu đầy đủ.
- [ ] `/devices`: 3 thiết bị active hiện đúng "ONLINE" + chấm xanh.
- [ ] `/home`: có banner demo.
- [ ] **Review với người trước khi sang Phase 2 (refactor).**

---

# Phase 2 — Nền tảng design system

## Task 5: Định nghĩa lại bộ design token cho khớp theme slate/blue hiện tại
**Mô tả:** Token shadcn hiện tại (`generated/webflow.css`) cho ra màu sai theme (card #191919, primary đen, background trắng). Trước khi refactor component sang token, phải override token trong `src/styles/global.css` để map về đúng palette slate/blue đang dùng. Đây là điều kiện tiên quyết của mọi task refactor sau.

**Cần làm:**
- Trong `src/styles/global.css`, thêm một block override (đặt SAU phần import và `:root`/`.dark` hiện có, để thắng độ ưu tiên). App luôn ở dark theme nên override trực tiếp `:root` cho đơn giản:
  ```css
  /* App dùng dark slate theme cố định — map token về palette thực tế đang dùng */
  :root {
    --background: #0f172a;        /* slate-900 */
    --foreground: #f8fafc;        /* slate-50  */
    --card: #1e293b;              /* slate-800 */
    --card-foreground: #f8fafc;
    --popover: #1e293b;
    --popover-foreground: #f8fafc;
    --primary: #2563eb;           /* blue-600 */
    --primary-foreground: #ffffff;
    --secondary: #334155;         /* slate-700 */
    --secondary-foreground: #f8fafc;
    --muted: #334155;             /* slate-700 */
    --muted-foreground: #94a3b8;  /* slate-400 */
    --accent: #1d4ed8;            /* blue-700 */
    --accent-foreground: #ffffff;
    --destructive: #dc2626;       /* red-600 */
    --border: #334155;            /* slate-700 */
    --input: #334155;
    --ring: #3b82f6;              /* blue-500 */
    --radius: 0.75rem;            /* khớp rounded-xl đang dùng nhiều */
  }
  ```
- Mục tiêu: sau khi thêm, các component shadcn (Button, Dialog, Input...) hiển thị đúng màu xanh/slate, KHÔNG ra màu đen/trắng.
- KHÔNG xoá import `generated/webflow.css` (vẫn cần cho font/biến khác).

**Acceptance criteria:**
- [ ] Component `<Button>` mặc định (`variant="default"`) hiển thị nền **xanh blue**, chữ trắng (không phải đen).
- [ ] `<Dialog>`/`<Input>` shadcn có nền slate tối, border slate, hợp theme.
- [ ] Các trang HIỆN TẠI (vẫn hardcode slate) trông KHÔNG đổi (vì màu token giờ trùng với slate).

**Verification:**
- [ ] `npm run build` PASS.
- [ ] Mở app → nút "Lưu" (TopicManagement đang dùng raw `bg-blue-600`) và nút shadcn `<Button>` (Devices delete modal) phải cùng tông xanh.
- [ ] Kiểm tra nhanh qua DevTools: `getComputedStyle(document.documentElement).getPropertyValue('--primary')` ≈ `#2563eb`.

**Dependencies:** None
**Files likely touched:** `src/styles/global.css`
**Estimated scope:** S
**Risk:** Trung bình — đổi token có thể ảnh hưởng component shadcn đang dùng. Test kỹ Dialog/Button/Input sau khi đổi.

---

## Task 6: Tạo lớp component dùng chung (PageHeader, Panel, StatCard, StatusBadge)
**Mô tả:** Trích các pattern lặp lại thành component dùng token, để các trang refactor sau chỉ việc dùng. Đặt ở `src/components/common/`.

**Cần làm — tạo 4 component:**

1. `src/components/common/PageHeader.jsx` — tiêu đề trang + mô tả + slot action bên phải:
   ```jsx
   export function PageHeader({ title, description, actions }) {
     return (
       <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
         <div>
           <h1 className="text-3xl font-bold text-foreground mb-2">{title}</h1>
           {description && <p className="text-muted-foreground">{description}</p>}
         </div>
         {actions && <div className="flex items-center gap-3">{actions}</div>}
       </div>
     );
   }
   ```
2. `src/components/common/Panel.jsx` — khung card/section chuẩn:
   ```jsx
   import { cn } from '@/lib/utils';
   export function Panel({ className, children, ...props }) {
     return (
       <div className={cn('bg-card text-card-foreground rounded-xl border border-border shadow-lg', className)} {...props}>
         {children}
       </div>
     );
   }
   ```
3. `src/components/common/StatCard.jsx` — KPI card (tách từ Home, dùng token; giữ prop `title,value,icon,color,subtitle` tương thích Home):
   - Giữ API props giống bản inline trong Home để thay 1-1.
   - Dùng `bg-card border-border` thay `bg-slate-800 border-slate-700`.
4. `src/components/common/StatusBadge.jsx` — badge trạng thái online/offline dùng `isOnline` từ Task 2:
   ```jsx
   import { isOnline } from '@/lib/deviceStatus';
   export function StatusBadge({ status }) {
     const online = isOnline(status);
     return (
       <span className="flex items-center gap-2">
         <span className={cn('w-2 h-2 rounded-full', online ? 'bg-green-500 animate-pulse' : 'bg-red-500')} />
         <span className={cn('text-sm font-medium', online ? 'text-green-500' : 'text-red-500')}>
           {online ? 'ONLINE' : 'OFFLINE'}
         </span>
       </span>
     );
   }
   ```
- Kiểm tra alias `@/` hoạt động (đã thấy `@/lib/utils` dùng trong `button.tsx` → alias OK; nếu file `.jsx` không nhận `@/`, dùng đường dẫn tương đối).

**Acceptance criteria:**
- [ ] 4 component tạo xong, export đúng, `npm run build` PASS.
- [ ] Component render độc lập không lỗi (chưa cần gắn vào trang).

**Verification:**
- [ ] `npm run build` PASS.
- [ ] Import thử `StatusBadge` vào 1 trang tạm để xác nhận render (rồi gỡ), hoặc verify ở Task 7.

**Dependencies:** Task 2 (deviceStatus), Task 5 (token)
**Files likely touched:** `src/components/common/*.jsx` (4 file mới)
**Estimated scope:** M

---

### ✅ Checkpoint B — sau Task 5–6
- [ ] Token khớp theme, app trông không đổi so với trước.
- [ ] 4 component dùng chung sẵn sàng, build PASS.

---

# Phase 3 — Refactor từng trang sang token + component dùng chung

> Mỗi task dưới đây là 1 trang. Làm tuần tự, mỗi trang xong build + xem trên browser rồi mới sang trang kế. Nguyên tắc thay class:
> `bg-slate-900`→`bg-background`, `bg-slate-800`→`bg-card` (qua `<Panel>`), `border-slate-700`→`border-border`, `text-white`→`text-foreground`, `text-slate-400`→`text-muted-foreground`, `bg-blue-600`→`bg-primary` + `text-primary-foreground`. GIỮ các màu semantic trạng thái (green/red/amber cho online/offline/cảnh báo) — KHÔNG token hoá chúng.

## Task 7: Refactor trang Home dùng PageHeader + StatCard + Panel
**Mô tả:** Thay block inline trong `Home.jsx` bằng component dùng chung.
**Cần làm:**
- Thay `<div className="flex items-center justify-between">...<h1>Home</h1>...` bằng `<PageHeader title="Home" description="Overview / tình trạng tổng quan hệ thống" actions={<...System Active badge...>} />`.
- Xoá `StatCard` định nghĩa inline, import từ `common/StatCard`.
- Bọc bảng "Latest Alerts" bằng `<Panel>`; thay `bg-slate-800 border-slate-700` → bỏ (Panel lo).
- Header bảng `bg-slate-900` → `bg-muted` hoặc giữ; row hover `hover:bg-slate-900` → `hover:bg-muted/50`.
- Giữ banner demo (Task 4).

**Acceptance criteria:**
- [ ] Home trông tương đương trước (hoặc đẹp hơn), không vỡ layout.
- [ ] Không còn `bg-slate-*`/`text-white` trực tiếp trong `Home.jsx` (trừ màu semantic green/red/amber).

**Verification:**
- [ ] `npm run build` PASS; `/home` hiển thị đúng.
- [ ] `grep -n "slate-" src/pages/Home.jsx` → chỉ còn (nếu có) chỗ thực sự cần.

**Dependencies:** Task 6
**Files likely touched:** `src/pages/Home.jsx`
**Estimated scope:** S

## Task 8: Refactor trang Devices (DeviceCard + Panel + StatusBadge)
**Mô tả:** Áp token + `StatusBadge` cho card thiết bị; thay khối skeleton/empty bằng token.
**Cần làm:**
- `DeviceCard`: footer dùng `<StatusBadge status={device.status} />`.
- Card container `bg-slate-800 border-slate-700` → `<Panel>` (hoặc class token). Search input `bg-slate-800 border-slate-700` → `bg-card border-border`.
- Modal xoá thiết bị tạm GIỮ NGUYÊN ở task này (sẽ thay bằng Dialog ở Task 11).
- Giữ FAB và các màu trạng thái.

**Acceptance criteria:**
- [ ] `/devices` hiển thị đúng, badge trạng thái dùng component chung.
- [ ] Không còn `bg-slate-*` trực tiếp (trừ semantic).

**Verification:**
- [ ] `npm run build` PASS; xem `/devices` đủ 3 card, badge ONLINE xanh.

**Dependencies:** Task 6
**Files likely touched:** `src/pages/Devices.jsx`
**Estimated scope:** M

## Task 9: Refactor Dashboard + DeviceDetail dùng Panel + token
**Mô tả:** Áp Panel/token cho 2 trang biểu đồ. Giữ màu chart (#3b82f6...) vì recharts cần giá trị màu cụ thể.
**Cần làm:**
- `GlobalDashboard.jsx`: `MetricBarChartCard` wrapper `bg-slate-800 border-slate-700` → `<Panel className="p-6">`. Header dùng `text-foreground`/`text-muted-foreground`. PageHeader cho tiêu đề.
- `DeviceDetail.jsx`: tương tự, các card thông tin + chart wrapper → Panel/token. PageHeader hoặc giữ nút back.
- Chart màu line/bar: GIỮ nguyên hex (recharts dùng prop `fill`/`stroke`).

**Acceptance criteria:**
- [ ] 2 trang hiển thị đúng, biểu đồ vẫn màu như cũ.
- [ ] Wrapper card dùng token.

**Verification:**
- [ ] `npm run build` PASS; `/dashboard` và `/devices/1` hiển thị đúng.

**Dependencies:** Task 6
**Files likely touched:** `src/pages/GlobalDashboard.jsx`, `src/pages/DeviceDetail.jsx`
**Estimated scope:** M

## Task 10: Refactor UserManagement + TopicManagement + Login dùng token
**Mô tả:** Áp token cho 3 trang còn lại. Login nên dùng `<Input>`/`<Button>` shadcn nếu nhanh, không thì token hoá class hiện tại.
**Cần làm:**
- `UserManagement.jsx`: card user, search, nút → token + PageHeader. Cân nhắc dùng `<Panel>` cho card user.
- `TopicManagement.jsx`: bảng, panel runtime, input, nút "Lưu" (`bg-blue-600`→`bg-primary`) → token. PageHeader.
- `Login.jsx`: input/nút → token (`focus:ring-blue-500`→`focus:ring-ring`, nút `bg-blue-600`→`bg-primary`). Giữ layout gradient.

**Acceptance criteria:**
- [ ] 3 trang hiển thị đúng, không vỡ; nút/đầu vào đồng bộ theme.

**Verification:**
- [ ] `npm run build` PASS; xem `/user-management`, `/topic-management`, `/login`.

**Dependencies:** Task 6
**Files likely touched:** `src/pages/UserManagement.jsx`, `src/pages/TopicManagement.jsx`, `src/pages/Login.jsx`
**Estimated scope:** M

## Task 10b (phát sinh): Token hoá nốt các trang/component còn lại
**Mô tả:** Để design system nhất quán TOÀN app (không chỗ token chỗ slate), đã token hoá thêm các file ngoài danh sách gốc:
`ChangePassword.jsx`, `Forbidden.jsx`, `ForgotPassword.jsx`, `GPSPage.jsx`, `Layout.jsx` (nav chính), `AddDeviceModal.jsx`, `AssignDeviceModal.jsx`, `ChangePasswordModal.jsx`, `AdminRoute.jsx`, `ProtectedRoute.jsx`.
**Giữ nguyên:** gradient nền `from-slate-900 via-slate-800 to-slate-900` ở Login/ForgotPassword (chủ ý thiết kế); màu semantic (green/red/amber/purple badge); màu chart recharts.
**Verify:** `grep -rnE "slate-[0-9]" src/pages src/components` chỉ còn gradient + comment. ✅ build PASS.

### ✅ Checkpoint C — sau Task 7–10
- [ ] Toàn bộ trang dùng token, đổi `--primary` 1 chỗ → đổi màu nhấn toàn app (test thử rồi revert).
- [ ] `grep -rn "bg-slate-" src/pages` chỉ còn các chỗ semantic chấp nhận được.
- [ ] App trông nhất quán, không vỡ layout ở 1440 / 768 / 375 px.

---

# Phase 4 — Accessibility & dọn dẹp

## Task 11: Thay modal tự chế bằng Dialog/AlertDialog shadcn
**Mô tả:** Modal xoá thiết bị (`Devices.jsx`) và `ChangePasswordModal.jsx` đang tự dựng `fixed inset-0` — thiếu focus-trap, ESC, aria. Thay bằng `<AlertDialog>` (xác nhận xoá) và `<Dialog>` (đổi mật khẩu) đã có ở `src/components/ui/`.
**Cần làm:**
- Modal xoá thiết bị → `<AlertDialog>`: giữ logic gõ "OK" để xác nhận + nút Huỷ/Xoá. Dùng `AlertDialogContent/Header/Title/Description/Footer/Cancel/Action`.
- `ChangePasswordModal.jsx` → `<Dialog>`: chuyển nội dung vào `DialogContent`. Giữ nguyên props/onClose.
- Xoá phần markup overlay tự chế tương ứng.

**Acceptance criteria:**
- [ ] Mở modal → focus tự nhảy vào trong; bấm ESC đóng; Tab không thoát ra ngoài modal.
- [ ] Logic xoá/đổi mật khẩu hoạt động y như cũ.

**Verification:**
- [ ] `npm run build` PASS.
- [ ] `/devices` → bấm thùng rác → dialog mở, ESC đóng, gõ "OK" + Xoá hoạt động.
- [ ] Bấm Tab trong dialog → focus quẩn trong dialog.

**Dependencies:** Task 5 (token để dialog đúng màu)
**Files likely touched:** `src/pages/Devices.jsx`, `src/components/ChangePasswordModal.jsx`
**Estimated scope:** M

## Task 12: Sửa `lang` document + dọn cảnh báo
**Mô tả:** `<html lang="en">` nhưng nội dung tiếng Việt → sai cho screen reader/SEO. Và dọn 2 warning React Router future flag (tuỳ chọn).
**Cần làm:**
- Sửa `app_service/index.html`: `<html lang="en">` → `<html lang="vi">`.
- (Tuỳ chọn) Trong `IoTApp.jsx`, thêm future flags cho Router để hết warning:
  ```jsx
  <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
  ```

**Acceptance criteria:**
- [ ] `document.documentElement.lang === 'vi'`.
- [ ] (Tuỳ chọn) Console không còn 2 warning future flag.

**Verification:**
- [ ] `npm run build` PASS; DevTools Console kiểm tra `document.documentElement.lang`.

**Dependencies:** None
**Files likely touched:** `app_service/index.html`, `src/components/IoTApp.jsx`
**Estimated scope:** XS

### ✅ Checkpoint cuối — sau toàn bộ (ĐÃ HOÀN TẤT & VERIFY trên production :80)
- [x] `npm run build` PASS (mọi task).
- [x] Đăng nhập → Home/Dashboard/Devices/DeviceDetail không lỗi.
- [x] Tiếng Việt có dấu toàn bộ (Dashboard, Topic đã verify).
- [x] Trạng thái thiết bị đúng (active→ONLINE xanh, đã verify trên Devices + DeviceDetail).
- [x] Modal xoá = AlertDialog: mở/ESC đóng/focus-trap hoạt động (đã verify).
- [x] `lang="vi"`, token đúng (--primary #2563eb, --card #1e293b), 1 <h1>, có <main>.
- [x] Nginx cache fix (index.html no-cache, assets immutable).
- [ ] Responsive 768/375px: chưa verify trực quan (cửa sổ Chrome không thu nhỏ được dưới ~1536px); code mobile-first đã có sẵn từ trước.
- [ ] (Còn lại) 1 input thiếu accessible name — nhỏ, có thể bổ sung sau.

## Tổng kết phạm vi đã làm
- Phase 0: Task 0 (.env.local cho dev — KHÔNG đụng .env production của docker).
- Phase 1: Task 1 (i18n), 2 (status active/online + deviceStatus.js), 3 (gỡ nút Turn On/Off giả + dead code), 4 (banner demo Home), 4b (nginx cache).
- Phase 2: Task 5 (override token slate/blue), 6 (PageHeader/Panel/StatCard/StatusBadge).
- Phase 3: Task 7–10 + 10b (token hoá TẤT CẢ trang + Layout + modal + route guard; giữ gradient Login, màu chart, màu semantic).
- Phase 4: Task 11 (modal xoá→AlertDialog, ChangePasswordModal→Dialog), 12 (lang=vi + router future flags).

---

## Rủi ro & giảm thiểu
| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Đổi token (Task 5) làm component shadcn đổi màu ngoài ý muốn | Cao | Test Button/Dialog/Input ngay sau Task 5; so sánh trước/sau |
| Refactor token làm vỡ màu semantic (online/offline) | TB | KHÔNG token hoá green/red/amber; chỉ token hoá slate/blue nền |
| `device_id` số vs chuỗi gây so sánh sai | TB | Luôn `String()` khi so khớp id (code hiện đã làm phần lớn) |
| Dev mode không gọi được API | Thấp | Task 0 tạo `.env`; hoặc test trực tiếp trên `localhost:80` (Docker) |
| Đổi nút Turn On/Off (Task 3) bỏ tính năng người dùng tưởng có | TB | Mặc định ẩn (phương án A); xác nhận với owner nếu cần điều khiển thật |

## Câu hỏi mở (cần người xác nhận khi tới task tương ứng)
- Task 3: chọn phương án A (ẩn nút) hay B (PATCH status thật)? — mặc định A.
- Có cần thêm test (Vitest/RTL) không? Hiện repo chưa có test runner → kế hoạch chỉ verify bằng build + thủ công.
