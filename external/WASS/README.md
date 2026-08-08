# WASS 外部依赖

WASS 是本项目的外部依赖，其上游仓库为：

<https://github.com/fbergama/wass>

## 管理规则

- 不将 WASS 源码复制或直接提交到本仓库。
- 不在本项目中修改 WASS 源码；需要变更时应在独立分支或 fork 中处理。
- 实验必须记录所用 WASS 的版本标签或提交哈希、构建环境和运行参数。
- 本目录默认忽略除本说明外的所有内容，可供本地检出或挂载 WASS。

## 本地安装示例

在不纳入版本控制的前提下，可执行：

```bash
git clone https://github.com/fbergama/wass.git external/WASS/source
git -C external/WASS/source checkout <tag-or-commit>
```

确定首个实验基线后，将 `<tag-or-commit>` 替换为固定版本，并在实验记录中保存该值。
