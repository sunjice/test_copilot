import { computed, type ComputedRef } from "vue"
import type { ChatMessage } from "@/api/chat/types"

/**
 * 消息分组：把连续的 assistant confirm_card 消息合并为一条气泡，
 * 使多任务创建卡片像多个工具调用一样，排列在同一条 AI 消息里，
 * 而不是每条卡片独立成一条消息。
 */

export type GroupItem =
  | { kind: "single"; msg: ChatMessage; key: string }
  | { kind: "confirm-group"; messages: ChatMessage[]; key: string }

/**
 * 对消息列表做分组。
 * @param messagesRef 消息列表的 Ref（或 getter）
 */
export function useMessageGrouping(
  messagesRef: ComputedRef<ChatMessage[]> | (() => ChatMessage[])
): ComputedRef<GroupItem[]> {
  const groupedMessages = computed<GroupItem[]>(() => {
    const list =
      typeof messagesRef === "function" ? messagesRef() : messagesRef.value
    const result: GroupItem[] = []
    let i = 0
    let autoIdx = 0
    while (i < list.length) {
      const msg = list[i]
      // 合并相邻的 confirm_card
      if (msg.role === "assistant" && msg.msg_type === "confirm_card") {
        const group: ChatMessage[] = [msg]
        let j = i + 1
        while (j < list.length) {
          const next = list[j]
          if (
            next.role === "assistant" &&
            next.msg_type === "confirm_card"
          ) {
            group.push(next)
            j++
          } else {
            break
          }
        }
        result.push({
          kind: "confirm-group",
          messages: group,
          key: `grp-${String(group[0]?.id ?? autoIdx++)}`,
        })
        i = j
        continue
      }
      const k = `s-${String(msg.id || `${msg.role}-${autoIdx++}-${msg.create_time}`)}`
      result.push({ kind: "single", msg, key: k })
      i++
    }
    return result
  })

  return groupedMessages
}
