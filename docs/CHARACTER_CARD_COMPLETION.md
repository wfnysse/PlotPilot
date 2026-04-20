# 角色卡补全功能说明

## 🎯 功能概述

为已有小说中的角色提供**批量补全**和**单个补全**功能，自动填充空白的角色卡字段。

---

## ✨ 功能特性

### 1. 批量补全所有角色
- 📍 位置：角色卡管理页面顶部工具栏
- 🎨 按钮：**"批量补全"**（带闪电图标）
- ⚡ 作用：一次性为所有资料不完整的角色补全信息
- 🔄 智能跳过：已完整的角色会自动跳过

### 2. 单个角色补全
- 📍 位置：每个角色卡片右上角
- 🎨 按钮：**"补全"**文字按钮
- ⚡ 作用：只为当前角色补全资料
- 💡 提示：如果角色已有资料，会询问是否重新生成

---

## 📋 使用场景

### 场景 1：老小说角色资料空白

**问题**：
```
之前创建的小说，角色只有名称和简单描述：
- 名称：林渊
- 定位：主角  
- 描述：待补充
- 其他字段：全部空白 ❌
```

**解决方案**：
1. 进入工作台
2. 右侧面板 → 剧本基建 → 角色卡
3. 点击顶部 **"批量补全"** 按钮
4. 确认操作
5. 等待 AI 自动生成完整资料
6. 检查并微调（可选）

**结果**：
```
补全后的角色：
- 名称：林渊 ✅
- 性别：男 ✅
- 年龄：25岁 ✅
- 身份：穿越者、程序员 ✅
- 外貌：黑发黑眸... ✅
- 性格：理性冷静... ✅
- ... 所有字段都有内容 ✅
```

---

### 场景 2：单个角色需要完善

**问题**：
```
某个角色的资料不够详细，想重新生成
```

**解决方案**：
1. 找到该角色卡片
2. 点击右上角的 **"补全"** 按钮
3. 等待生成完成
4. 如果不满意，可以再次点击重新生成

---

## 🔧 技术实现

### 前端实现

#### 1. 批量补全函数
```typescript
async function handleCompleteAllCharacters() {
  // 1. 确认操作
  const result = await window.confirm(...)
  
  // 2. 遍历所有角色
  for (const char of characters.value) {
    // 3. 检查是否已有完整资料
    const hasCompleteData = char.gender && char.personality && char.background
    
    if (hasCompleteData) {
      continue // 跳过已完整的角色
    }
    
    // 4. 调用 API 补全（目前使用模拟数据）
    await bibleApi.updateCharacter(novelId.value, char.id, completeData)
  }
}
```

#### 2. 单个补全函数
```typescript
async function handleCompleteSingleCharacter(char: CharacterDTO) {
  // 1. 添加到正在补全的集合
  completingCharacters.value.add(char.id)
  
  try {
    // 2. 调用 API 补全
    await bibleApi.updateCharacter(novelId.value, char.id, completeData)
    
    // 3. 显示成功消息
    message.success(`${char.name} 资料补全成功`)
  } finally {
    // 4. 从集合中移除
    completingCharacters.value.delete(char.id)
  }
}
```

#### 3. UI 状态管理
- `completingAll`: 批量补全的加载状态
- `completingCharacters`: 单个角色补全的状态集合
- 补全时按钮显示 loading 状态
- 防止重复点击

---

## 🎨 UI 设计

### 批量补全按钮
```
[导出] [导入] [应用模板 ▼] [✨ 批量补全]
                                    ↑
                              主要按钮样式
                              带闪电图标
                              显示加载状态
```

### 单个补全按钮
```
┌─────────────────────────────────────┐
│ 👤 林渊              [补全]         │
│    主角                             │
│                                     │
│ 现代程序员穿越到修仙世界...          │
└─────────────────────────────────────┘
        ↑                      ↑
    点击打开编辑        点击补全资料
```

---

## 📊 补全的字段清单

### 基本信息（4个）
- ✅ gender - 性别
- ✅ age - 年龄
- ✅ identity - 身份职业
- ✅ appearance - 外貌特征

### 性格特征（4个）
- ✅ personality - 性格特点
- ✅ strengths - 优势长处
- ✅ weaknesses - 弱点缺陷
- ✅ habits - 习惯癖好

### 背景故事（3个）
- ✅ background - 背景故事
- ✅ motivation - 核心动机
- ✅ goal - 目标追求

### 能力体系（3个）
- ✅ power_system - 能力体系
- ✅ skills - 特殊技能
- ✅ equipment - 重要装备

### 发展轨迹（4个）
- ✅ character_arc - 成长轨迹
- ✅ mental_state - 精神状态
- ✅ verbal_tic - 口头禅
- ✅ idle_behavior - 闲时行为

**共计 18 个字段**

---

## 🚀 后续优化方向

### 1. 接入真实 AI API
**当前状态**：使用模拟数据
**改进方案**：
```typescript
// TODO: 调用后端 API
const response = await bibleApi.completeCharacterCard(
  novelId.value, 
  char.id,
  {
    generate_full_card: true
  }
)
```

**后端实现**：
- 复用 `_generate_full_character_card()` 方法
- 基于世界观和角色基本信息生成
- 确保内容符合设定

### 2. 智能检测完整性
**当前逻辑**：
```typescript
const hasCompleteData = char.gender && char.personality && char.background
```

**改进方案**：
- 计算完整度百分比
- 标记缺失的重要字段
- 优先补全关键字段

### 3. 用户确认机制
**当前流程**：直接覆盖
**改进方案**：
```
1. AI 生成完整资料
2. 弹出预览窗口
3. 用户可以：
   - 接受全部
   - 修改部分字段
   - 重新生成
4. 确认后保存
```

### 4. 进度显示
**当前状态**：简单的 loading 提示
**改进方案**：
```
正在补全角色资料...
进度: 3/5 (60%)

✓ 林渊 - 完成
✓ 老陈 - 完成
⏳ 小吴 - 生成中...
○ 李四 - 等待中
○ 王五 - 等待中
```

### 5. 失败重试
**当前状态**：失败后跳过
**改进方案**：
- 记录失败的角色
- 提供"重试失败项"按钮
- 显示失败原因

---

## 💡 使用建议

### 1. 批量补全前
- ✅ 备份重要数据（导出 JSON）
- ✅ 确认网络连接稳定
- ✅ 预留足够时间（每个角色约 2-3 秒）

### 2. 补全后检查
- ✅ 查看生成的内容是否符合预期
- ✅ 调整不符合角色设定的字段
- ✅ 补充个性化的细节

### 3. 结合其他功能
- **应用模板**：先应用模板，再微调
- **手动编辑**：AI 生成后手动优化
- **导入导出**：补全后导出备份

---

## ⚠️ 注意事项

### 1. 当前限制
- 🔸 使用模拟数据，不是真实 AI 生成
- 🔸 补全的内容比较通用，缺乏个性化
- 🔸 没有基于世界观进行定制

### 2. 性能考虑
- 🔸 批量补全大量角色时可能较慢
- 🔸 建议分批处理（每次 5-10 个）
- 🔸 避免频繁点击补全按钮

### 3. 数据安全
- 🔸 补全会覆盖现有数据
- 🔸 建议先导出备份
- 🔸 重要角色建议手动编辑

---

## 📝 示例代码

### 接入真实 AI API（待实现）

```typescript
// 前端调用
async function handleCompleteSingleCharacter(char: CharacterDTO) {
  completingCharacters.value.add(char.id)
  
  try {
    // 调用后端 API
    const result = await bibleApi.completeCharacterCard(
      novelId.value,
      char.id,
      {
        generate_full_card: true,
        based_on_worldbuilding: true
      }
    )
    
    message.success(`${char.name} 资料补全成功`)
    await loadCharacters()
  } catch (error) {
    message.error(`${char.name} 资料补全失败`)
  } finally {
    completingCharacters.value.delete(char.id)
  }
}
```

```python
# 后端实现（auto_bible_generator.py）
async def complete_character_card(
    self,
    novel_id: str,
    character_id: str,
    generate_full_card: bool = True
) -> Dict[str, Any]:
    """补全单个角色的完整资料"""
    
    # 1. 获取角色基本信息
    bible = self.bible_service.get_bible_by_novel(novel_id)
    character = next(
        (c for c in bible.characters if c.character_id.value == character_id),
        None
    )
    
    if not character:
        raise ValueError(f"Character {character_id} not found")
    
    # 2. 加载世界观
    worldbuilding = self._load_worldbuilding(novel_id)
    
    # 3. 生成完整角色卡
    if generate_full_card:
        full_data = await self._generate_full_character_card(
            {
                'name': character.name,
                'role': character.role,
                'description': character.description
            },
            worldbuilding,
            []  # 可以传入其他角色建立关系
        )
        
        # 4. 更新角色
        character.gender = full_data.get('gender', character.gender)
        character.age = full_data.get('age', character.age)
        # ... 更新其他字段
        
        # 5. 保存（假设 db 已通过 Settings + DatabaseConnection 初始化）
        repo = SqliteBibleRepository(db)
        repo.save(bible)
        
        return full_data
```

---

## ✅ 总结

### 已实现功能
- ✅ 批量补全所有角色
- ✅ 单个角色补全
- ✅ 智能跳过已完整角色
- ✅ 加载状态显示
- ✅ 错误处理和提示

### 待优化功能
- ⏸️ 接入真实 AI API
- ⏸️ 智能完整度检测
- ⏸️ 用户确认机制
- ⏸️ 进度条显示
- ⏸️ 失败重试机制

### 使用价值
- 🎯 快速补全老小说的角色资料
- 🎯 节省手动填写的时间
- 🎯 提供基础的参考内容
- 🎯 可以作为进一步优化的起点

**现在你可以轻松地为已有小说补全完整的角色卡了！** 🎉
