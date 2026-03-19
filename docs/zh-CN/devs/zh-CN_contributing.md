# 贡献指南

## 开始前的准备

建议先阅读以下文档：

1. [综合技术参考](zh-CN_agent.md) — 了解项目架构和技术栈
2. [代码规范](zh-CN_code_standards.md) — 了解代码风格要求
3. [项目结构](zh-CN_project_structure.md) — 了解目录组织

## 贡献工作流程

### 1. 配置本地开发环境

```bash
# 克隆仓库
git clone <repo-url>
cd team-project-26spring-26s-5

# 安装所有依赖
task init

# 配置环境变量
cp .env.example .env
```

### 2. 创建 Issue（可选）

在 GitHub 上创建 Issue 描述你要做的事情。

### 3. 创建功能分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/your-bugfix-name
```

分支命名规范：
- `feature/xxx` — 新功能
- `fix/xxx` — Bug 修复
- `docs/xxx` — 文档更新
- `refactor/xxx` — 重构

### 4. 开发和测试

```bash
# 开发过程中频繁运行检查
bash scripts/check.sh

# 或运行特定包的测试
task test:core
task test:gui
```

### 5. 提交代码

使用约定式提交格式：

```bash
git add .
git commit -m "feat(core): add new tool registration method"
```

### 6. 推送并创建 PR

```bash
git push origin feature/your-feature-name
```

在 GitHub 上创建 Pull Request，填写 PR 模板。

### 7. 代码审查

- CI 会自动运行检查
- 根据反馈修改代码
- 获得 LGTM 后合并

### 8. 清理

```bash
git checkout main
git pull origin main
git branch -d feature/your-feature-name
```

## 提交前检查清单

- [ ] 运行 `bash scripts/check.sh` 所有检查通过
- [ ] Commit message 遵循约定式提交规范
- [ ] 源代码中没有中文字符
- [ ] 新增功能有对应的测试
- [ ] 如果修改了公共 API，更新了文档
