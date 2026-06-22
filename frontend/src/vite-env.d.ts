/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BASE_PATH?: string;
  readonly VITE_VIBE_CLOUD_THREE_PAGE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
