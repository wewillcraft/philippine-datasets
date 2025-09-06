#!/usr/bin/env -S deno run -A --watch=static/,routes/,islands/,components/

import dev from "$fresh/dev.ts";
import config from "./fresh.config.ts";

import { load } from "@std/dotenv";
await load({ export: true });

await dev(import.meta.url, "./main.ts", config);
