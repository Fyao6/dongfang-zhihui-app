# 东方智慧公网 Demo

本目录为现有 R4 前后台的云端适配器。保留原 APP 与管理界面，使用 Cloudflare Worker、D1 和 R2 托管。原本机 Python/SQLite 版本仍在 ../r4，数据互不混用。

## 源码与构建

- prepare.py：从本项目现有 R4 构建页面及自有素材生成 generated/ 和 public/assets/；没有导入本机数据库。
- lib/eastern-api.ts：现有 HTTP 接口的云端实现；worker/index.ts：界面和接口入口。
- db/schema.ts 与 drizzle/：D1 表结构及不可变迁移。
- .openai/hosting.json：唯一站点身份与 D1/R2 绑定。后续更新复用其中 project_id，不要另建站点。
- 已提交 generated/，远端构建不需要原完整交付包。修改原界面后重新运行 prepare.py，再构建和回归。

## 管理员和数据

首次请求使用运行环境中的 DEMO_ADMIN_HASH 创建 demo_admin；公开接口不能初始化管理员。使用 PBKDF2 SHA256 100000 次派生、随机盐、摘要会话、HTTPS HttpOnly Cookie。环境变量为密码摘要，不能放明文密码、API Key 到源码或构建产物。

D1 存储账号、会话、配置、内容、记录、审核及审计；R2 保存上传文件。公网只初始化项目已有展示内容，测试账号与本机私密数据均不上传。媒体授权按现有发布与会员访问规则执行。

## 验证与交付边界

06 目录的“公网适配全量回归.cjs”对 127.0.0.1:8877 的独立 Worker/D1/R2 环境验证全部页面及管理操作。默认包含后台界面回归，管理员测试凭据只在被忽略的 .env.test 中。测试数据库绝不可发布。

真实 AI 要另配有效模型和密钥；设备要另接供应商；正式支付尚未接入。现有本机偏好和部分学习记录保持浏览器存储逻辑，不代表所有数据均支持跨设备同步。

发布使用 Sites 插件标准 source push → archive → save version → deploy 流程。发布前删除 dist/server/.dev.vars；禁止归档 .env*、.dev.vars*、.wrangler、.sites-runtime、node_modules、.git 及任何私有数据库。新建管理员后变更 DEMO_ADMIN_HASH 不会覆盖现有账号密码，需实施专门的密码轮换流程。

## Netlify 访问入口

用户要求自行注册 Netlify 账号，使用可供国内直接访问的 netlify.app 网址。源码增加 netlify.toml、prepare-netlify.mjs 与 worker/netlify-api.js。运行 node prepare-netlify.mjs 后，仅上传 .netlify/public 中的页面素材，API Edge Function 位于生成的 .netlify/edge-source。

数据和权限校验继续由已经上线的原云服务负责。Netlify 的 /api/* 在服务器侧转发，浏览器只访问新站的同源接口；先校验请求Origin，再转发身份Cookie和请求正文；不包含管理员密码或后台特权密钥。原云后端不能关闭，否则新的后台接口会不可用。

这不是全部迁移到Netlify数据库。更新前后台业务仍应更新对应原云服务；页面/网关变更重新部署Netlify。站点身份分别保存：Sites使用.openai/hosting.json，Netlify使用.netlify/state.json，不能互相覆盖。

Netlify CLI 27.16.1 放在 .sites-runtime/netlify-tool。其匿名部署明确禁止Edge Functions，所以完整前后台需用户本人注册并授权CLI。不要交付仅有静态页面的匿名站点作为本需求的完成结果。无代理实际访问和完整后台上线验收未通过前，不能宣称国内入口已完成。
