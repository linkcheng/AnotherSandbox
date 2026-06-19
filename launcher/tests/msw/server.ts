// msw node server（vitest 环境用 setupServer）
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
