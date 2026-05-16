# 🧋 zz.fb520.site - 菲比 Bot 赞助页

> 菲比 Bot 鸣潮免费分享机器人的赞助/投喂页面，公益运行，感谢每一位支持者 💛

## ✨ 功能

- 🎨 **赞助页面** — 展示微信/支付宝/QQ 收款码，支持一键切换
- 📋 **赞助名单** — 自动展示所有赞助者（名字 + 金额），前 3 位默认展示，其余可展开
- 📊 **运营概览** — 实时显示总收入、总支出、盈亏状态
- 🔐 **管理后台** — 密码保护，支持：
  - ➕ 添加赞助者
  - ✏️ 编辑赞助者名字/金额
  - 🗑️ 删除赞助者
  - 💰 修改总支出（总收入自动从名单计算）
  - 📊 实时预览盈亏变化

## 📁 文件结构

```
├── index.html          # 赞助主页（前台展示）
├── admin.html          # 管理后台（密码保护）
├── app.py              # 后端 API 服务（Flask）
├── assets/
│   ├── phoebe-avatar.jpg   # 菲比头像
│   ├── bg-phoebe.jpg       # 背景图
│   ├── wechat.jpg          # 微信收款码
│   ├── alipay.jpg          # 支付宝收款码
│   └── qq.jpg              # QQ 收款码
└── README.md
```

## 🚀 部署说明

### 后端 API

```bash
# 安装依赖
pip install flask

# 运行（建议用 systemd 托管）
python app.py
# 默认监听 127.0.0.1:5100
```

### 数据存储

- 赞助名单：`data/sponsors.json`
- 财务数据：`data/finance.json`

### Nginx/OpenResty 反代

将 `/api/` 路径反代到后端：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:5100/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 🔑 管理后台

访问 `https://你的域名/admin.html`，输入管理密码即可进入。

### API 接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/sponsors` | 获取赞助列表 | 无 |
| POST | `/api/sponsors` | 添加赞助者 | 需密码 |
| PUT | `/api/sponsors/{id}` | 编辑赞助者 | 需密码 |
| DELETE | `/api/sponsors/{id}` | 删除赞助者 | 需密码 |
| GET | `/api/finance` | 获取财务数据 | 无 |
| PUT | `/api/finance` | 更新支出 | 需密码 |

认证方式：请求头 `X-Admin-Password` 或 JSON body 中的 `password` 字段。

## 💡 特性

- 总收入自动从赞助名单计算（添加/编辑/删除后自动重算）
- 管理后台实时预览盈亏变化
- 前台赞助名单超过 3 人自动折叠，用户可展开查看
- 响应式设计，移动端友好
- 毛玻璃 UI 风格，和菲比 Bot 官网统一

## 📝 License

MIT

---

**菲比 Bot** · 鸣潮免费分享机器人 · 公益运行 💛
