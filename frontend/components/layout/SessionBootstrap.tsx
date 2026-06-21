"use client";

import { useEffect } from "react";
import { useAppStore } from "@/stores/useAppStore";
import {
  getPersistedSessionId,
  hydrateSessionFromServer,
} from "@/lib/sessionBootstrap";

/** 启动时尝试恢复上次会话（对标 job-ops 本地优先） */
export default function SessionBootstrap() {
  const store = useAppStore();

  useEffect(() => {
    const sid = getPersistedSessionId();
    if (!sid || store.sessionId) return;
    hydrateSessionFromServer(sid, {
      setSessionId: store.setSessionId,
      setCurrentMarkdown: store.setCurrentMarkdown,
      setOriginalMarkdown: store.setOriginalMarkdown,
      setParsedResume: store.setParsedResume,
      setJdText: store.setJdText,
      setJdAnalysis: store.setJdAnalysis,
      setMatchResult: store.setMatchResult,
      setSuggestions: store.setSuggestions,
      setKnowledgeBase: store.setKnowledgeBase,
      setFinalizedMarkdown: store.setFinalizedMarkdown,
      setFinalizeStatus: store.setFinalizeStatus,
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
