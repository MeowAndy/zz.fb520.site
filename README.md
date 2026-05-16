# zz.fb520.site - 菲比 Bot 赞助页

赞助官网，展示赞助二维码和赞助名单。

## 结构

- `index.html` - 赞助主页（含赞助名单展示）
- `admin.html` - 赞助管理页面（密码保护）
- `assets/` - 静态资源（头像、二维码图片）
- `data/sponsors.json` - 赞助者数据
- `api/app.py` - 后端 API 服务（Flask）

## 部署

后端 API 通过 systemd 服务 `zz-sponsor-api` 运行在 `127.0.0.1:5100`，OpenResty 反代 `/api/` 路径。

## API

- `GET /api/sponsors` - 获取赞助列表
- `POST /api/sponsors` - 添加赞助者（需 X-Admin-Password 头）
- `DELETE /api/sponsors/{id}` - 删除赞助者（需 X-Admin-Password 头）
