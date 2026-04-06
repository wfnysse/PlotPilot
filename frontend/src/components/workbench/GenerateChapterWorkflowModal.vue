<template>
  <n-modal
    v-model:show="show"
    preset="card"
    style="width: min(820px, 98vw)"
    :mask-closable="false"
    :segmented="{ content: true, footer: 'soft' }"
    title="完整工作流撰稿"
  >
    <template #header-extra>
      <n-text depth="3" style="font-size: 12px">上下文 + 流式 + 一致性检验</n-text>
    </template>

    <n-alert v-if="!result" type="info" :show-icon="true" class="gwm-intro">
      与侧栏「对话」互补：对话负责多轮讨论与工具编排；此处按大纲生成整章、流式展示、一致性校验后保存到章节。
    </n-alert>

    <n-space vertical :size="14" class="gwm-body">
      <n-form-item label="章节" :show-feedback="false">
            <n-select
              v-model:value="chapterNumber"
              :options="chapterOptions"
              placeholder="选择章号"
              :disabled="generating"
            />
          </n-form-item>
          <n-form-item :show-feedback="false">
            <template #label>
              <n-space :size="6" align="center">
                <span>本章大纲</span>
                <n-tag v-if="analyzingScene" size="tiny" type="info" round>🔍 场景分析中…</n-tag>
                <n-tag v-else-if="cachedSceneAnalysis" size="tiny" type="success" round>✓ 场景已预分析</n-tag>
              </n-space>
            </template>
            <n-input
              v-model:value="outline"
              type="textarea"
              placeholder="粘贴或编写本章大纲（必填）；失去焦点后自动预分析场景"
              :autosize="{ minRows: 5, maxRows: 14 }"
              :disabled="generating"
              @blur="autoAnalyzeScene"
            />
          </n-form-item>

          <n-form-item v-if="!result" label="生成方式" :show-feedback="false">
            <n-space align="center" :size="12">
              <n-switch v-model:value="useStream" :disabled="generating" />
              <n-text depth="3">流式（实时阶段 + 正文逐段显示，推荐）</n-text>
            </n-space>
          </n-form-item>

          <template v-if="!result && generating && useStream">
            <n-space vertical :size="10">
              <n-progress
                type="line"
                :percentage="streamProgress"
                :processing="streamProgress < 100"
                :height="10"
                indicator-placement="inside"
              />
              <n-text depth="3">{{ phaseLabel }}</n-text>
              <n-input
                v-model:value="editedContent"
                type="textarea"
                placeholder="正文将在此流式出现…"
                :autosize="{ minRows: 8, maxRows: 22 }"
                readonly
              />
              <n-button size="small" secondary @click="stopStream">停止生成</n-button>
            </n-space>
          </template>

          <n-space v-if="!result" justify="end" :size="10">
            <n-button @click="close">取消</n-button>
            <n-button type="primary" :loading="generating" :disabled="generating" @click="runGenerate">生成</n-button>
          </n-space>

          <template v-else>
            <n-alert v-if="saveError" type="error" :title="saveError" />
            <ConsistencyReportPanel
              :report="result.consistency_report"
              :token-count="result.token_count"
              @location-click="onLocationClick"
            />

            <!-- 俗套句式命中 -->
            <n-collapse v-if="result.style_warnings && result.style_warnings.length > 0" class="cliche-collapse">
              <n-collapse-item :title="`⚠️ 俗套句式命中 ${result.style_warnings.length} 处（点击展开）`" name="cliche">
                <n-space vertical :size="6">
                  <n-alert
                    v-for="(w, i) in result.style_warnings"
                    :key="i"
                    :type="w.severity === 'warning' ? 'warning' : 'info'"
                    :title="w.pattern"
                    style="font-size: 12px"
                  >
                    「{{ w.text }}」
                  </n-alert>
                </n-space>
              </n-collapse-item>
            </n-collapse>

            <n-form-item label="正文（可编辑后再保存）" :show-feedback="false">
              <n-input
                v-model:value="editedContent"
                type="textarea"
                :autosize="{ minRows: 12, maxRows: 28 }"
                :disabled="saving"
              />
            </n-form-item>
            <n-space justify="end" :size="10">
              <n-button @click="resetResult">重新生成</n-button>
              <n-button type="primary" :loading="saving" @click="saveToChapter">保存到章节</n-button>
            </n-space>
          </template>
    </n-space>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import {
  workflowApi,
  consumeGenerateChapterStream,
  analyzeScene,
  type GenerateChapterWorkflowResponse,
} from '../../api/workflow'
import { chapterApi } from '../../api/chapter'
import ConsistencyReportPanel from './ConsistencyReportPanel.vue'

export interface ChapterOption {
  id: number
  title: string
}

const props = defineProps<{
  show: boolean
  slug: string
  chapters: ChapterOption[]
  defaultChapterId?: number | null
}>()

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'saved'): void
}>()

const message = useMessage()
const dialog = useDialog()

const show = computed({
  get: () => props.show,
  set: (v: boolean) => emit('update:show', v),
})

const chapterNumber = ref<number | null>(null)
const outline = ref('')
const generating = ref(false)
const saving = ref(false)
const saveError = ref('')
const result = ref<GenerateChapterWorkflowResponse | null>(null)
const editedContent = ref('')
const useStream = ref(true)
const streamProgress = ref(0)
const phaseLabel = ref('')
let streamAbort: AbortController | null = null
let chunkCount = 0

// SceneDirector 自动预分析（大纲 blur 时触发）
const cachedSceneAnalysis = ref<Record<string, unknown> | null>(null)
const analyzingScene = ref(false)

async function autoAnalyzeScene() {
  const o = outline.value.trim()
  const n = chapterNumber.value
  if (!o || n == null || analyzingScene.value) return
  analyzingScene.value = true
  try {
    const analysis = await analyzeScene(props.slug, n, o)
    cachedSceneAnalysis.value = analysis as Record<string, unknown>
  } catch {
    // 失败静默，生成时仍可正常进行
    cachedSceneAnalysis.value = null
  } finally {
    analyzingScene.value = false
  }
}

const chapterOptions = computed(() =>
  props.chapters.map(c => ({
    label: `第${c.id}章 ${c.title ? c.title.slice(0, 16) : ''}`,
    value: c.id,
  }))
)

watch(
  () => [props.show, props.chapters, props.defaultChapterId] as const,
  () => {
    if (!props.show) return
    const ch = props.chapters
    if (!ch.length) {
      chapterNumber.value = null
      return
    }
    const def = props.defaultChapterId
    if (def != null && ch.some(x => x.id === def)) {
      chapterNumber.value = def
    } else if (chapterNumber.value == null || !ch.some(x => x.id === chapterNumber.value)) {
      chapterNumber.value = ch[0].id
    }
  },
  { immediate: true }
)

watch(
  () => props.show,
  v => {
    if (!v) {
      generating.value = false
      saveError.value = ''
      streamAbort?.abort()
      streamAbort = null
      result.value = null
      editedContent.value = ''
      outline.value = ''
      streamProgress.value = 0
      phaseLabel.value = ''
    }
  }
)

function close() {
  if (generating.value) {
    dialog.warning({
      title: '确认关闭',
      content: '当前仍有生成任务进行中，关闭后将中断。确定关闭？',
      positiveText: '关闭并中断',
      negativeText: '继续等待',
      onPositiveClick: () => {
        streamAbort?.abort()
        emit('update:show', false)
      },
    })
    return
  }
  streamAbort?.abort()
  emit('update:show', false)
}

function resetResult() {
  result.value = null
  editedContent.value = ''
  saveError.value = ''
  streamProgress.value = 0
  phaseLabel.value = ''
  cachedSceneAnalysis.value = null
}

function phaseToProgress(phase: string): number {
  const map: Record<string, number> = {
    planning: 12,
    context: 28,
    llm: 38,
    post: 92,
  }
  return map[phase] ?? streamProgress.value
}

function stopStream() {
  streamAbort?.abort()
  streamAbort = null
  generating.value = false
  phaseLabel.value = '已停止'
}

async function runGenerate() {
  const n = chapterNumber.value
  const o = outline.value.trim()
  if (n == null) {
    message.warning('请选择章节')
    return
  }
  if (!o) {
    message.warning('请填写本章大纲')
    return
  }
  generating.value = true
  saveError.value = ''
  editedContent.value = ''
  streamProgress.value = 4
  phaseLabel.value = '准备中…'
  chunkCount = 0

  if (useStream.value) {
    streamAbort = new AbortController()
    await consumeGenerateChapterStream(
      props.slug,
      { chapter_number: n, outline: o, scene_director_result: cachedSceneAnalysis.value ?? undefined },
      {
        signal: streamAbort.signal,
        onPhase: phase => {
          streamProgress.value = phaseToProgress(phase)
          const labels: Record<string, string> = {
            planning: '叙事与故事线规划…',
            context: '构建上下文（圣经 / 摘要等）…',
            llm: '模型正在生成本章正文…',
            post: '一致性检查与收尾…',
          }
          phaseLabel.value = labels[phase] ?? phase
        },
        onChunk: text => {
          chunkCount += 1
          editedContent.value += text
          streamProgress.value = Math.min(88, 38 + Math.min(chunkCount * 0.35, 50))
        },
        onDone: data => {
          result.value = data
          editedContent.value = data.content || ''
          streamProgress.value = 100
          phaseLabel.value = '完成'
          message.success('生成完成')
        },
        onError: msg => {
          message.error(msg || '生成失败')
        },
      }
    )
    streamAbort = null
    generating.value = false
    if (result.value) return
    return
  }

  try {
    const data = await workflowApi.generateChapterWithContext(props.slug, {
      chapter_number: n,
      outline: o,
    })
    result.value = data
    editedContent.value = data.content || ''
    message.success('生成完成')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    message.error(err.response?.data?.detail || err.message || '生成失败')
  } finally {
    generating.value = false
  }
}

async function saveToChapter() {
  const n = chapterNumber.value
  if (n == null) return
  const content = editedContent.value
  saving.value = true
  saveError.value = ''
  try {
    await chapterApi.updateChapter(props.slug, n, { content })
    message.success('已保存到章节')
    emit('saved')
    emit('update:show', false)
    result.value = null
    editedContent.value = ''
    outline.value = ''
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    saveError.value = err.response?.data?.detail || err.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function onLocationClick(location: number) {
  message.info(`问题位置标记：${location}（可在章节视图内对照）`)
}
</script>

<style scoped>
.gwm-body {
  width: 100%;
}
.gwm-intro {
  font-size: 13px;
}
.cliche-collapse {
  margin: 4px 0;
}
</style>
