# Cursor Rules: 代码编写规范

## 一、通用规则（所有文件）

### 1.1 行尾空格
- **规则**: 不允许行尾有多余空格
- **检查工具**: `trailing-whitespace`
- **示例**:
  ```python
  # ✅ 正确：行尾无空格
  name = "John"

  # ❌ 错误：行尾有空格（此处有空格）
  name = "John"
  ```

### 1.2 文件结尾
- **规则**: 所有文件必须以空行结尾
- **检查工具**: `end-of-file-fixer`

### 1.3 行尾格式
- **规则**: 统一使用 LF（Unix 格式），禁止混用 CRLF
- **检查工具**: `mixed-line-ending`

### 1.4 大文件检查
- **规则**: 单文件大小不超过 500KB
- **检查工具**: `check-added-large-files`

### 1.5 合并冲突
- **规则**: 禁止提交包含 `<<<<<<<`, `=======`, `>>>>>>>` 的文件
- **检查工具**: `check-merge-conflict`

### 1.6 敏感信息
- **规则**: 禁止提交私钥等敏感信息
- **检查工具**: `detect-private-key`

---

## 二、Python 代码规则

### 2.1 Black 格式化规则

#### 缩进
- **规则**: 使用 4 个空格缩进，禁止使用 Tab
- **示例**:
  ```python
  def my_function():
      if condition:
          return True  # ✅ 4 空格缩进
  ```

#### 行宽
- **规则**: 最多 88 字符
- **示例**:
  ```python
  # ✅ 正确：拆分长行
  result = some_long_function_name(arg1, arg2, arg3,
                                  arg4, arg5)
  ```

#### 字符串
- **规则**: 统一使用双引号，除非包含双引号
- **示例**:
  ```python
  name = "John"           # ✅ 双引号
  message = 'He said: "Hello"'  # ✅ 内部有双引号时用单引号
  ```

#### 尾部逗号
- **规则**: 多行列表/字典/元组末尾必须有逗号
- **示例**:
  ```python
  my_list = [
      "item1",
      "item2",
      "item3",  # ✅ 尾部逗号
  ]
  ```

#### 导入排序
- **规则**: 按标准库 → 第三方库 → 本地库分组，每组按字母排序
- **示例**:
  ```python
  import os
  import sys

  import requests
  from pydantic import BaseModel

  from .utils import helper
  ```

### 2.2 Ruff 代码检查规则

| 规则码 | 说明 |
|--------|------|
| **F401** | 禁止未使用的导入 |
| **F821** | 禁止未定义的变量 |
| **E501** | 行宽不超过 88 字符 |
| **W293** | 禁止行尾空格 |
| **E1101** | 禁止访问不存在的属性 |
| **B018** | 禁止不必要的布尔转换 |

---

## 三、YAML 配置文件规则

### 3.1 基本规则

#### 缩进
- **规则**: 使用 2 个空格缩进
- **示例**:
  ```yaml
  database:
    host: localhost  # ✅ 2 空格缩进
    port: 5432
  ```

#### 键名格式
- **规则**: 小写，使用连字符或下划线
- **示例**:
  ```yaml
  api-key: "abc123"    # ✅ 连字符
  max_retries: 3       # ✅ 下划线
  ```

#### 字符串
- **规则**: 简单值可省略引号，复杂值用双引号
- **示例**:
  ```yaml
  name: MyApp                    # ✅ 简单值
  description: "Multi-line\ntext"  # ✅ 复杂值用双引号
  ```

#### 列表格式
- **规则**: 每行一个元素
- **示例**:
  ```yaml
  items:
    - item1
    - item2
    - item3
  ```

### 3.2 禁止项
- ❌ 禁止使用制表符缩进
- ❌ 禁止连续空行

---

## 四、Markdown 文档规则

### 4.1 格式规范

#### 标题
- **规则**: 标题前后空一行
- **示例**:
  ```markdown
  # 一级标题

  段落内容。

  ## 二级标题
  ```

#### 段落
- **规则**: 段落之间空一行

#### 列表
- **规则**: 使用连字符 `-` 作为列表标记
- **示例**:
  ```markdown
  - 列表项1
  - 列表项2
  ```

#### 代码
- **规则**: 行内代码用反引号，代码块用三个反引号
- **示例**:
  ```markdown
  行内代码：`code`

  ```python
  # 代码块
  print("Hello")
  ```
  ```

#### 链接与图片
- **规则**: 使用标准 markdown 格式
- **示例**:
  ```markdown
  [链接文本](URL)
  ![替代文本](图片URL)
  ```

---

## 五、提交前自检清单

### 5.1 命令行检查

```bash
# 1. Python 代码格式化（自动修复）
cd ai-saas-week4
python3 -m black benchmark/ tests/
python3 -m ruff check benchmark/ tests/ --fix

# 2. YAML 格式检查
yamllint config.yaml docker-compose.yml

# 3. 运行测试
python3 -m pytest tests/ -v

# 4. 检查文件结尾
find . -type f -name "*.py" -exec sh -c 'tail -c1 "{}" | read -r || echo "Missing newline: {}"' \;

# 5. 检查尾随空格
grep -rn " $" --include="*.py" --include="*.yaml" --include="*.md" .
```

### 5.2 VS Code 配置

创建 `.vscode/settings.json`:

```json
{
    "editor.tabSize": 4,
    "editor.insertSpaces": true,
    "editor.rulers": [88],
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter"
    },
    "[yaml]": {
        "editor.defaultFormatter": "redhat.vscode-yaml"
    },
    "[markdown]": {
        "editor.defaultFormatter": "esbenp.prettier-vscode"
    },
    "python.linting.ruffEnabled": true
}
```

---

## 六、常见问题修复

| 错误信息 | 原因 | 修复方法 |
|----------|------|----------|
| `trailing whitespace` | 行尾有空格 | 删除行尾空格 |
| `No newline at end of file` | 文件未以空行结尾 | 在文件末尾添加空行 |
| `E501 line too long` | 行超过 88 字符 | 拆分长行 |
| `F401 'xxx' imported but unused` | 导入未使用 | 删除未使用的导入 |
| `YAML syntax error` | YAML 格式错误 | 检查缩进和语法 |

---

## 七、总结

遵循以上规则编写代码，可以确保：
1. ✅ 通过所有 pre-commit 检查
2. ✅ 代码风格统一
3. ✅ 减少代码审查中的格式问题
4. ✅ 提高代码质量和可读性

---

**版本**: v1.0
**适用项目**: ai-saas-week4
**最后更新**: 2026-05-12
