"use client";

import { useEffect, useId, useRef, useState } from "react";
import type mermaid from "mermaid";

type MermaidMindmapProps = {
  code: string;
};

export default function MermaidMindmap({ code }: MermaidMindmapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);
  const mermaidRef = useRef<typeof mermaid | null>(null);
  const [error, setError] = useState("");
  const reactId = useId();
  const idRef = useRef(`mermaid-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`);

  useEffect(() => {
    if (!code.trim()) {
      setError("");
      return;
    }
    let cancelled = false;

    const render = async () => {
      try {
        if (!mermaidRef.current) {
          mermaidRef.current = (await import("mermaid")).default;
        }
        if (!initializedRef.current) {
          mermaidRef.current.initialize({ startOnLoad: false, theme: "neutral" });
          initializedRef.current = true;
        }
        const { svg } = await mermaidRef.current.render(idRef.current, code);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setError("");
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "渲染失败");
        }
      }
    };

    render();

    return () => {
      cancelled = true;
    };
  }, [code]);

  if (!code.trim()) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">
        尚未生成思维导图
      </div>
    );
  }

  return (
    <div className="overflow-auto min-h-[400px]">
      {error ? (
        <div className="text-center py-8">
          <div className="text-sm text-amber-700 mb-2">
            导图渲染失败，可复制源码到 Mermaid 工具查看
          </div>
          <div className="text-xs text-gray-500 mb-1">{error}</div>
        </div>
      ) : (
        <div ref={containerRef} className="flex justify-center" />
      )}
    </div>
  );
}
