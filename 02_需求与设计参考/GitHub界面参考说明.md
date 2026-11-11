# 本轮 GitHub 界面参考与实施取舍

用户要求：上一版科技感过于儿戏，去 GitHub 查找实际 APP 参考。用户没有指定某个仓库或认可本轮配色。

实际读取的来源：
- [Anytype iOS](https://github.com/anyproto/anytype-swift)，包括 [颜色体系](https://github.com/anyproto/anytype-swift/blob/develop/Anytype/Sources/DesignSystem/COLOR_SYSTEM.md) 和 [字体映射](https://github.com/anyproto/anytype-swift/blob/develop/Anytype/Sources/PresentationLayer/Common/TYPOGRAPHY_MAPPING.md)。其按背景、文字、形状、操作状态区分语义颜色，并单独规定标题、正文及辅助字层级。本轮采用这类组织方式，未直接搬用其品牌设计或源码。
- [Ente](https://github.com/ente/ente)，包括 [共享日夜主题](https://github.com/ente/ente/blob/main/mobile/packages/ui/lib/theme/ente_theme_data.dart) 和 [Ensu 主题规则](https://github.com/ente/ente/blob/main/android/apps/ensu/app/src/main/java/io/ente/ensu/designsystem/Theme.kt)。后者分别定义表面、文字、边框、操作色和 4/8/12/16/20/24/32 间距，控件圆角保持克制。本轮参考其层级、节奏和状态管理方式，独立编写本项目样式。
- [AppFlowy](https://github.com/AppFlowy-IO/AppFlowy)：核对了仓库与 README，未将其作为已完成截图核对的视觉依据。

访问边界：浏览器未获准打开 raw.githubusercontent.com 图片，未通过其他方式绕过获取图片。因此没有把未经查看的远程图片写为视觉验收证据。提交标识、具体读取路径及源码文本存于同目录 GitHub界面参考记录.json。

本轮实施：
1. 以石墨黑与雾白为日夜表面，电光绿只用于焦点和主要操作；移除紫色星球、轨道、玻璃光晕。
2. 每日一句以文字为主，少量原创等距曲线作为背景。所有图形由本项目 HTML/SVG/CSS 绘制，无外部素材依赖。
3. 三大地图入口统一编号、图标、名称和一句用途；内页为两行四项动作，辅助设备入口置后。
4. 五项首页快捷功能处收尾；固定底部导航；音乐和课程使用紧凑列表；个人页偏好按需展开。
5. 后台自定义封面继续可用，配套文字颜色与遮罩；计时方块、长条、拖动磁吸及自动累计不变。

验收：本轮全量回归记录与实际手机视口截图保存于06_验证与后续工作，源码与构建仍在原项目目录。自动化检查不能代替用户对视觉的最终评价，也不能代替真实手机及供应商接入验收。
