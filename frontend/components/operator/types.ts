/** What the agent loop panel highlights, and the caption saying why. */
export type Highlight = { nodes: Set<string>; caption: string };

export type HighlightRefs = (refs: string[], caption: string) => void;
