<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    title="确认角色列表"
    style="width: 1000px; max-width: 95vw;"
    :segmented="{ content: true, footer: 'soft' }"
    :closable="false"
  >
    <div class="character-confirmation">
      <n-alert type="info" class="mb-4">
        AI 已生成 {{ characters.length }} 个角色，请确认角色名称和信息。您可以编辑、添加或删除角色。
      </n-alert>

      <!-- 角色列表 -->
      <div class="character-list">
        <div 
          v-for="(char, index) in characters" 
          :key="index"
          class="character-item"
        >
          <n-card size="small" class="character-card">
            <template #header>
              <n-space align="center" justify="space-between">
                <n-space align="center">
                  <n-avatar 
                    :size="40" 
                    :style="{ backgroundColor: getAvatarColor(char.name) }"
                  >
                    {{ char.name ? char.name.charAt(0) : '?' }}
                  </n-avatar>
                  <div>
                    <div class="char-index">角色 {{ index + 1 }}</div>
                  </div>
                </n-space>
                <n-button 
                  text 
                  type="error" 
                  @click="removeCharacter(index)"
                  :disabled="characters.length <= 1"
                >
                  删除
                </n-button>
              </n-space>
            </template>

            <n-form
              :model="char"
              label-placement="left"
              label-width="80"
              size="small"
            >
              <n-form-item label="角色名称" required>
                <n-input 
                  v-model:value="char.name" 
                  placeholder="请输入角色名称"
                />
              </n-form-item>
              
              <n-form-item label="角色定位">
                <n-select
                  v-model:value="char.role"
                  :options="[
                    { label: '主角', value: '主角' },
                    { label: '配角', value: '配角' },
                    { label: '反派', value: '反派' },
                    { label: '导师', value: '导师' },
                    { label: '路人', value: '路人' },
                  ]"
                  placeholder="选择角色定位"
                />
              </n-form-item>
              
              <n-form-item label="描述">
                <n-input
                  v-model:value="char.description"
                  type="textarea"
                  placeholder="角色描述"
                  :autosize="{ minRows: 2, maxRows: 3 }"
                />
              </n-form-item>
            </n-form>
          </n-card>
        </div>
      </div>

      <!-- 添加角色按钮 -->
      <n-button 
        dashed 
        block 
        class="mt-4"
        @click="addCharacter"
      >
        + 添加角色
      </n-button>
    </div>

    <template #footer>
      <n-space justify="space-between">
        <n-text depth="3">
          共 {{ characters.length }} 个角色
        </n-text>
        <n-space>
          <n-button @click="handleCancel">取消</n-button>
          <n-checkbox v-model:checked="generateFullCard">
            生成完整角色卡
          </n-checkbox>
          <n-button 
            type="primary" 
            @click="handleConfirm"
            :loading="confirming"
            :disabled="!isValid"
          >
            确认并保存
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { 
  NModal, NAlert, NSpace, NCard, NAvatar, NButton, 
  NForm, NFormItem, NInput, NSelect, NCheckbox, NText,
  useMessage
} from 'naive-ui'
import { bibleApi } from '@/api/bible'

interface CharacterData {
  name: string
  role?: string
  description?: string
}

const props = defineProps<{
  novelId: string
  initialCharacters?: CharacterData[]
}>()

const emit = defineEmits<{
  (e: 'confirm', characters: CharacterData[], generateFullCard: boolean): void
  (e: 'cancel'): void
}>()

const message = useMessage()

const visible = ref(false)
const characters = ref<CharacterData[]>([])
const confirming = ref(false)
const generateFullCard = ref(true)

// 验证是否所有角色都有名称
const isValid = computed(() => {
  return characters.value.every(char => char.name && char.name.trim())
})

// 显示弹窗
function show(initialChars?: CharacterData[]) {
  if (initialChars && initialChars.length > 0) {
    characters.value = initialChars.map(char => ({
      name: char.name || '',
      role: char.role || '',
      description: char.description || ''
    }))
  } else {
    // 默认添加一个空角色
    characters.value = [{ name: '', role: '', description: '' }]
  }
  visible.value = true
}

// 隐藏弹窗
function hide() {
  visible.value = false
}

// 添加角色
function addCharacter() {
  characters.value.push({ name: '', role: '', description: '' })
}

// 删除角色
function removeCharacter(index: number) {
  if (characters.value.length > 1) {
    characters.value.splice(index, 1)
  }
}

// 获取头像颜色
function getAvatarColor(name: string): string {
  const colors = [
    '#18a058', '#2080f0', '#f0a020', '#d03050',
    '#9759de', '#13c2c2', '#fa541c', '#52c41a'
  ]
  if (!name) return '#d0d0d0'
  const index = name.charCodeAt(0) % colors.length
  return colors[index]
}

// 确认
async function handleConfirm() {
  if (!isValid.value) {
    message.warning('请确保所有角色都有名称')
    return
  }

  confirming.value = true
  try {
    // 调用后端 API 确认并保存角色
    const result = await bibleApi.confirmCharacters(props.novelId, {
      characters: characters.value,
      generate_full_card: generateFullCard.value
    })

    message.success(`成功保存 ${result.characters_saved} 个角色`)
    
    emit('confirm', characters.value, generateFullCard.value)
    hide()
  } catch (error) {
    message.error('保存失败，请重试')
    console.error(error)
  } finally {
    confirming.value = false
  }
}

// 取消
function handleCancel() {
  emit('cancel')
  hide()
}

// 暴露方法给父组件
defineExpose({
  show,
  hide
})
</script>

<style scoped>
.character-confirmation {
  max-height: 60vh;
  overflow-y: auto;
}

.mb-4 {
  margin-bottom: 16px;
}

.mt-4 {
  margin-top: 16px;
}

.character-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.character-item {
  transition: all 0.2s;
}

.character-card {
  border: 1px solid #e8e8e8;
}

.char-index {
  font-size: 12px;
  color: #999;
}
</style>
