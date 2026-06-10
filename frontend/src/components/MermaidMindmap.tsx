"use client";

import { useEffect, useRef, useState } from "react";

type MermaidMindmapProps = {
  code: string;
};

export default function MermaidMindmap({ code }: MermaidMindmapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const idRef = useRef(`mermaid-${Math.random().toString(36).slice(2, 9)}`);

  useEffect(() => {
    if (!code.trim()) {
      setError("");
      return;
    }
    let cancelled = false;

    const render = async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "neutral" });
        const { svg } = await mermaid.render(idRef.current, code);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setError("");
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e.message || "渲染失败");
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
