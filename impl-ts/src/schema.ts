/**
 * Payload shape validation against the normative JSON Schemas of the current spec folder.
 *
 * Spec: §10.3 (the schema files are normative for payload shape), §12.12 (`info.data` binding schemas).
 * Impl: schemas are read from `v1.0/…/schemas` at start-up rather than copied, so this
 * implementation cannot drift from the spec folder.
 */
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { ValidateFunction } from "ajv";
import type { Json } from "./did.js";

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CORE_SCHEMAS = join(REPO, "v1.0", "dsip-schemas-v1.0", "dsip-schemas", "schemas");

/** Schema files that are not message types (`key-agreement-delegation` is a credential, §7.3). */
const NOT_MESSAGES = new Set(["envelope", "message", "webrtc-info-data", "dtmf-info-data", "key-agreement-delegation"]);

/** `info.about` → the binding schema its `data` must satisfy. Spec: §12.12 */
const INFO_BINDINGS: Record<string, string> = {
  "transport:webrtc": "webrtc-info-data",
  "media:dtmf": "dtmf-info-data",
};

/** A set of compiled schemas, addressed by file stem (`invite`, `hello`, …). */
export class SchemaSet {
  private readonly validators = new Map<string, ValidateFunction>();

  constructor(dir: string = CORE_SCHEMAS) {
    // Impl: `format` is an annotation in draft 2020-12 unless a vocabulary opts in; not asserted.
    const ajv = new Ajv2020({ strict: false, validateFormats: false, allErrors: false });
    const files = readdirSync(dir).filter((f) => f.endsWith(".schema.json"));
    const docs = files.map((f) => [f, JSON.parse(readFileSync(join(dir, f), "utf8"))] as const);
    for (const [, doc] of docs) ajv.addSchema(doc);
    for (const [f, doc] of docs) {
      this.validators.set(f.slice(0, -".schema.json".length), ajv.getSchema(doc.$id) ?? ajv.compile(doc));
    }
  }

  /** True when `name` is a core message type with a schema. */
  isMessageType(name: string): boolean {
    return this.validators.has(name) && !NOT_MESSAGES.has(name);
  }

  /** True when a schema named `name` exists. */
  has(name: string): boolean {
    return this.validators.has(name);
  }

  /** Validate `value` against schema `name`. */
  valid(name: string, value: Json): boolean {
    const v = this.validators.get(name);
    if (!v) throw new Error(`no schema named ${name}`);
    return v(value) === true;
  }

  /**
   * Validate a message payload, including `info.data` for an implemented binding.
   *
   * Spec: §12.12 — an unimplemented `about` leaves `data` unchecked: ignored, never rejected.
   */
  validMessage(type: string, payload: { [k: string]: Json }): boolean {
    if (!this.valid(type, payload)) return false;
    if (type === "info" && typeof payload["about"] === "string") {
      const binding = INFO_BINDINGS[payload["about"]];
      if (binding && "data" in payload) return this.valid(binding, payload["data"]!);
    }
    return true;
  }
}
