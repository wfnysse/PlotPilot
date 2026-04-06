<template>
  <div class="sandbox-panel">
    <n-space vertical :size="12">
      <n-alert type="info" :show-icon="true" style="font-size: 12px">
        <strong>写</strong>：挂起或审计时可改锚点字段；<strong>读</strong>：生成正文节拍时作为高优先级 System 提示注入声线与小动作。
      </n-alert>

      <!-- 角色锚点 + 试生成 -->
      <n-card title="角色锚点 · 试生成对话" size="small" :bordered="true">
        <n-space vertical :size="10">
          <n-alert
            v-if="characters.length === 0"
            type="warning"
            :show-icon="true"
            style="font-size: 12px"
          >
            当前 Bible 中<strong>没有角色</strong>：请打开侧栏「剧本基建」→ Story Bible，添加或生成角色后再回到此处选择。
          </n-alert>
          <n-space :size="8" wrap align="center">
            <n-select
              v-model:value="selectedCharacterId"
              :options="characterOptions"
              placeholder="选择 Bible 角色"
              filterable
              clearable
              style="min-width: 180px"
              size="small"
            />
            <n-button size="small" secondary :loading="anchorLoading" :disabled="!selectedCharacterId" @click="loadAnchor">
              载入锚点
            </n-button>
          </n-space>

          <template v-if="anchor">
            <n-form-item label="心理状态" label-placement="top" :show-feedback="false">
              <n-input v-model:value="editMental" size="small" placeholder="如：心理受创、亢奋" />
            </n-form-item>
            <n-form-item label="口头禅" label-placement="top" :show-feedback="false">
              <n-input v-model:value="editVerbal" size="small" />
            </n-form-item>
            <n-form-item label="待机动作" label-placement="top" :show-feedback="false">
              <n-input v-model:value="editIdle" size="small" placeholder="如：摸剑柄、转笔" />
            </n-form-item>
            <n-form-item label="场景提示" label-placement="top" :show-feedback="false">
              <n-input
                v-model:value="scenePrompt"
                type="textarea"
                size="small"
                placeholder="写一句场面/冲突，测试声线"
                :autosize="{ minRows: 2, maxRows: 5 }"
              />
            </n-form-item>
            <n-button
              type="primary"
              size="small"
              :loading="genLoading"
              :disabled="!scenePrompt.trim()"
              @click="runGenerate"
            >
              生成对话
            </n-button>
            <n-card v-if="generatedLine" size="small" :bordered="true" title="输出">
              <n-text style="font-size: 13px; line-height: 1.6">{{ generatedLine }}</n-text>
            </n-card>
          </template>
        </n-space>
      </n-card>

      <!-- 筛选区 -->
      <n-card title="对话白名单筛选" size="small" :bordered="false">
        <n-space vertical :size="8">
          <n-space :size="8" wrap>
            <n-form-item label="章节号" label-placement="left" label-width="54" :show-feedback="false">
              <n-input-number
                v-model:value="filterChapter"
                :min="1"
                clearable
                placeholder="全部"
                style="width: 90px"
                size="small"
              />
            </n-form-item>
            <n-form-item label="说话人" label-placement="left" label-width="54" :show-feedback="false">
              <n-input
                v-model:value="filterSpeaker"
                placeholder="全部"
                clearable
                size="small"
                style="width: 120px"
              />
            </n-form-item>
          </n-space>
          <n-button type="primary" size="small" :loading="loading" @click="loadWhitelist">查询</n-button>
        </n-space>
      </n-card>

      <!-- 结果 -->
      <div v-if="result !== null">
        <n-space align="center" justify="space-between" style="margin-bottom: 6px">
          <n-text strong>共 {{ result.total_count }} 条对话</n-text>
          <n-input
            v-model:value="searchText"
            size="tiny"
            placeholder="关键词搜索…"
            clearable
            style="width: 140px"
          />
        </n-space>

        <n-spin :show="loading">
          <n-scrollbar style="max-height: 420px">
            <n-space vertical :size="6" style="padding-right: 4px">
              <n-card
                v-for="d in filteredDialogues"
                :key="d.dialogue_id"
                size="small"
                :bordered="true"
                style="background: var(--n-color)"
              >
                <template #header>
                  <n-space align="center" :size="6">
                    <n-tag type="info" size="tiny" round>第{{ d.chapter }}章</n-tag>
                    <n-tag type="error" size="tiny" round>{{ d.speaker }}</n-tag>
                    <n-space :size="4">
                      <n-tag
                        v-for="tag in d.tags"
                        :key="tag"
                        size="tiny"
                        round
                      >{{ tag }}</n-tag>
                    </n-space>
                  </n-space>
                </template>
                <n-space vertical :size="4">
                  <n-blockquote style="margin: 0; font-size: 13px; line-height: 1.6">{{ d.content }}</n-blockquote>
                  <n-text depth="3" style="font-size: 11px">{{ d.context }}</n-text>
                </n-space>
              </n-card>
              <n-empty v-if="filteredDialogues.length === 0" description="无匹配对话" />
            </n-space>
          </n-scrollbar>
        </n-spin>
      </div>

      <n-empty v-else-if="!loading" description="点击「查询」载入对话白名单" />
    </n-space>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkbenchRefreshStore } from '../../stores/workbenchRefreshStore'
import { useMessage } from 'naive-ui'
import { sandboxApi } from '../../api/sandbox'
import type { DialogueWhitelistResponse, DialogueEntry, CharacterAnchor } from '../../api/sandbox'
import { bibleApi } from '../../api/bible'
import type { CharacterDTO } from '../../api/bible'

const props = defineProps<{ slug: string }>()
const message = useMessage()

const loading = ref(false)
const result = ref<DialogueWhitelistResponse | null>(null)
const filterChapter = ref<number | null>(null)
const filterSpeaker = ref('')
const searchText = ref('')

const characters = ref<CharacterDTO[]>([])
const selectedCharacterId = ref<string | null>(null)
const anchor = ref<CharacterAnchor | null>(null)
const anchorLoading = ref(false)
const genLoading = ref(false)
const editMental = ref('')
const editVerbal = ref('')
const editIdle = ref('')
const scenePrompt = ref('')
const generatedLine = ref('')

const characterOptions = computed(() =>
  characters.value.map(c => ({ label: c.name || c.id, value: c.id }))
)

async function loadCharacters() {
  try {
    characters.value = await bibleApi.listCharacters(props.slug)
  } catch {
    characters.value = []
  }
}

async function loadAnchor() {
  const id = selectedCharacterId.value
  if (!id) return
  anchorLoading.value = true
  try {
    const a = await sandboxApi.getCharacterAnchor(props.slug, id)
    anchor.value = a
    editMental.value = a.mental_state || ''
    editVerbal.value = a.verbal_tic || ''
    editIdle.value = a.idle_behavior || ''
    generatedLine.value = ''
  } catch {
    message.error('载入锚点失败（需 Bible 中存在该角色）')
    anchor.value = null
  } finally {
    anchorLoading.value = false
  }
}

async function runGenerate() {
  const id = selectedCharacterId.value
  if (!id || !scenePrompt.value.trim()) return
  genLoading.value = true
  generatedLine.value = ''
  try {
    const res = await sandboxApi.generateDialogue({
      novel_id: props.slug,
      character_id: id,
      scene_prompt: scenePrompt.value.trim(),
      mental_state: editMental.value || undefined,
      verbal_tic: editVerbal.value || undefined,
    })
    generatedLine.value = res.dialogue
  } catch {
    message.error('生成失败')
  } finally {
    genLoading.value = false
  }
}

watch(selectedCharacterId, () => {
  anchor.value = null
  generatedLine.value = ''
})

watch(
  () => props.slug,
  () => {
    void loadCharacters()
    anchor.value = null
    generatedLine.value = ''
  }
)

onMounted(() => void loadCharacters())

const filteredDialogues = computed<DialogueEntry[]>(() => {
  if (!result.value) return []
  const kw = searchText.value.trim().toLowerCase()
  if (!kw) return result.value.dialogues
  return result.value.dialogues.filter(d =>
    d.content.toLowerCase().includes(kw) ||
    d.speaker.toLowerCase().includes(kw) ||
    d.context.toLowerCase().includes(kw)
  )
})

const loadWhitelist = async () => {
  loading.value = true
  try {
    result.value = await sandboxApi.getDialogueWhitelist(
      props.slug,
      filterChapter.value ?? undefined,
      filterSpeaker.value.trim() || undefined
    )
  } catch {
    message.error('查询失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

const refreshStore = useWorkbenchRefreshStore()
const { deskTick } = storeToRefs(refreshStore)
watch(deskTick, async () => {
  await loadCharacters()
  if (result.value !== null) {
    await loadWhitelist()
  }
})
</script>

<style scoped>
.sandbox-panel {
  padding: 10px 12px;
  height: 100%;
  overflow-y: auto;
}
</style>
