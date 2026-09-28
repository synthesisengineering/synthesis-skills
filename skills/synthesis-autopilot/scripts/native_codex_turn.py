"""Bounded typed observations for one owned managed Codex turn.

Schema is a pinned subset of the actual vendor app-server export. This module
validates observations; it never admits a process, permission, effect or receipt.
Unknown methods/fields are gaps, not inferred successful native work.
"""

SCHEMA_SHA256 = "871046f308da617d6cbfb372ff0260a778d8b959ae7eca8757a2edcb4c5f3900"
SCHEMAS = {
    "autoApprovalReview/strictReviewRequired": {
        "$ref": "#/definitions/StrictReviewRequiredNotification"
    },
    "error": {"$ref": "#/definitions/ErrorNotification"},
    "hook/completed": {"$ref": "#/definitions/HookCompletedNotification"},
    "hook/started": {"$ref": "#/definitions/HookStartedNotification"},
    "item/agentMessage/delta": {"$ref": "#/definitions/AgentMessageDeltaNotification"},
    "item/autoApprovalReview/completed": {
        "$ref": "#/definitions/ItemGuardianApprovalReviewCompletedNotification"
    },
    "item/autoApprovalReview/started": {
        "$ref": "#/definitions/ItemGuardianApprovalReviewStartedNotification"
    },
    "item/commandExecution/outputDelta": {
        "$ref": "#/definitions/CommandExecutionOutputDeltaNotification"
    },
    "item/commandExecution/terminalInteraction": {
        "$ref": "#/definitions/TerminalInteractionNotification"
    },
    "item/completed": {"$ref": "#/definitions/ItemCompletedNotification"},
    "item/fileChange/outputDelta": {
        "$ref": "#/definitions/FileChangeOutputDeltaNotification"
    },
    "item/fileChange/patchUpdated": {
        "$ref": "#/definitions/FileChangePatchUpdatedNotification"
    },
    "item/mcpToolCall/progress": {
        "$ref": "#/definitions/McpToolCallProgressNotification"
    },
    "item/plan/delta": {"$ref": "#/definitions/PlanDeltaNotification"},
    "item/reasoning/summaryPartAdded": {
        "$ref": "#/definitions/ReasoningSummaryPartAddedNotification"
    },
    "item/reasoning/summaryTextDelta": {
        "$ref": "#/definitions/ReasoningSummaryTextDeltaNotification"
    },
    "item/reasoning/textDelta": {
        "$ref": "#/definitions/ReasoningTextDeltaNotification"
    },
    "item/started": {"$ref": "#/definitions/ItemStartedNotification"},
    "thread/status/changed": {"$ref": "#/definitions/ThreadStatusChangedNotification"},
    "thread/tokenUsage/updated": {
        "$ref": "#/definitions/ThreadTokenUsageUpdatedNotification"
    },
    "turn/completed": {"$ref": "#/definitions/TurnCompletedNotification"},
    "turn/diff/updated": {"$ref": "#/definitions/TurnDiffUpdatedNotification"},
    "turn/plan/updated": {"$ref": "#/definitions/TurnPlanUpdatedNotification"},
    "turn/started": {"$ref": "#/definitions/TurnStartedNotification"},
}
DEFINITIONS = {
    "AbsolutePathBuf": {"type": "string"},
    "AdditionalFileSystemPermissions": {
        "properties": {
            "entries": {
                "items": {"$ref": "#/definitions/FileSystemSandboxEntry"},
                "type": ["array", "null"],
            },
            "globScanMaxDepth": {"minimum": 1.0, "type": ["integer", "null"]},
            "read": {
                "items": {"$ref": "#/definitions/LegacyAppPathString"},
                "type": ["array", "null"],
            },
            "write": {
                "items": {"$ref": "#/definitions/LegacyAppPathString"},
                "type": ["array", "null"],
            },
        },
        "type": "object",
    },
    "AdditionalNetworkPermissions": {
        "properties": {"enabled": {"type": ["boolean", "null"]}},
        "type": "object",
    },
    "AgentMessageDelivery": {"enum": ["async"], "type": "string"},
    "AgentMessageDeltaNotification": {
        "properties": {
            "delta": {"type": "string"},
            "itemId": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["delta", "itemId", "threadId", "turnId"],
        "type": "object",
    },
    "AsyncUserInputQuestion": {
        "additionalProperties": False,
        "properties": {
            "options": {"items": {"type": "string"}, "type": ["array", "null"]}
        },
        "required": ["title"],
        "type": "object",
    },
    "AutoReviewDecisionSource": {"enum": ["agent"], "type": "string"},
    "ByteRange": {
        "properties": {
            "end": {"minimum": 0.0, "type": "integer"},
            "start": {"minimum": 0.0, "type": "integer"},
        },
        "required": ["end", "start"],
        "type": "object",
    },
    "CodexErrorInfo": {
        "oneOf": [
            {
                "enum": [
                    "contextWindowExceeded",
                    "sessionBudgetExceeded",
                    "usageLimitExceeded",
                    "rateLimitExceeded",
                    "serverOverloaded",
                    "cyberPolicy",
                    "misalignmentPolicyViolation",
                    "internalServerError",
                    "unauthorized",
                    "badRequest",
                    "threadRollbackFailed",
                    "sandboxError",
                    "other",
                ],
                "type": "string",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "httpConnectionFailed": {
                        "properties": {
                            "httpStatusCode": {
                                "minimum": 0.0,
                                "type": ["integer", "null"],
                            }
                        },
                        "type": "object",
                    }
                },
                "required": ["httpConnectionFailed"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "responseStreamConnectionFailed": {
                        "properties": {
                            "httpStatusCode": {
                                "minimum": 0.0,
                                "type": ["integer", "null"],
                            }
                        },
                        "type": "object",
                    }
                },
                "required": ["responseStreamConnectionFailed"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "responseStreamDisconnected": {
                        "properties": {
                            "httpStatusCode": {
                                "minimum": 0.0,
                                "type": ["integer", "null"],
                            }
                        },
                        "type": "object",
                    }
                },
                "required": ["responseStreamDisconnected"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "responseTooManyFailedAttempts": {
                        "properties": {
                            "httpStatusCode": {
                                "minimum": 0.0,
                                "type": ["integer", "null"],
                            }
                        },
                        "type": "object",
                    }
                },
                "required": ["responseTooManyFailedAttempts"],
                "type": "object",
            },
            {
                "additionalProperties": False,
                "properties": {
                    "activeTurnNotSteerable": {
                        "properties": {
                            "turnKind": {"$ref": "#/definitions/NonSteerableTurnKind"}
                        },
                        "required": ["turnKind"],
                        "type": "object",
                    }
                },
                "required": ["activeTurnNotSteerable"],
                "type": "object",
            },
        ]
    },
    "CollabAgentState": {
        "properties": {
            "message": {"type": ["string", "null"]},
            "status": {"$ref": "#/definitions/CollabAgentStatus"},
        },
        "required": ["status"],
        "type": "object",
    },
    "CollabAgentStatus": {
        "enum": [
            "pendingInit",
            "running",
            "interrupted",
            "completed",
            "errored",
            "shutdown",
            "notFound",
        ],
        "type": "string",
    },
    "CollabAgentTool": {
        "enum": [
            "spawnAgent",
            "sendInput",
            "resumeAgent",
            "wait",
            "closeAgent",
            "sendMessage",
            "followupTask",
            "interruptAgent",
            "listAgents",
        ],
        "type": "string",
    },
    "CollabAgentToolCallStatus": {
        "enum": ["inProgress", "completed", "failed", "interrupted"],
        "type": "string",
    },
    "CommandAction": {
        "oneOf": [
            {
                "properties": {
                    "command": {"type": "string"},
                    "name": {"type": "string"},
                    "path": {"$ref": "#/definitions/LegacyAppPathString"},
                    "type": {"enum": ["read"], "type": "string"},
                },
                "required": ["command", "name", "path", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "command": {"type": "string"},
                    "path": {"type": ["string", "null"]},
                    "type": {"enum": ["listFiles"], "type": "string"},
                },
                "required": ["command", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "command": {"type": "string"},
                    "path": {"type": ["string", "null"]},
                    "query": {"type": ["string", "null"]},
                    "type": {"enum": ["search"], "type": "string"},
                },
                "required": ["command", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "command": {"type": "string"},
                    "type": {"enum": ["unknown"], "type": "string"},
                },
                "required": ["command", "type"],
                "type": "object",
            },
        ]
    },
    "CommandExecutionOutputDeltaNotification": {
        "properties": {
            "delta": {"type": "string"},
            "itemId": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["delta", "itemId", "threadId", "turnId"],
        "type": "object",
    },
    "CommandExecutionSource": {
        "enum": ["agent", "userShell", "unifiedExecStartup", "unifiedExecInteraction"],
        "type": "string",
    },
    "CommandExecutionStatus": {
        "enum": ["inProgress", "completed", "failed", "declined"],
        "type": "string",
    },
    "DynamicToolCallOutputContentItem": {
        "oneOf": [
            {
                "properties": {
                    "text": {"type": "string"},
                    "type": {"enum": ["inputText"], "type": "string"},
                },
                "required": ["text", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "imageUrl": {"type": "string"},
                    "type": {"enum": ["inputImage"], "type": "string"},
                },
                "required": ["imageUrl", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "audioUrl": {"type": "string"},
                    "type": {"enum": ["inputAudio"], "type": "string"},
                },
                "required": ["audioUrl", "type"],
                "type": "object",
            },
        ]
    },
    "DynamicToolCallStatus": {
        "enum": ["inProgress", "completed", "failed"],
        "type": "string",
    },
    "ErrorNotification": {
        "properties": {
            "error": {"$ref": "#/definitions/TurnError"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
            "willRetry": {"type": "boolean"},
        },
        "required": ["error", "threadId", "turnId", "willRetry"],
        "type": "object",
    },
    "FileChangeOutputDeltaNotification": {
        "properties": {
            "delta": {"type": "string"},
            "itemId": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["delta", "itemId", "threadId", "turnId"],
        "type": "object",
    },
    "FileChangePatchUpdatedNotification": {
        "properties": {
            "changes": {
                "items": {"$ref": "#/definitions/FileUpdateChange"},
                "type": "array",
            },
            "itemId": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["changes", "itemId", "threadId", "turnId"],
        "type": "object",
    },
    "FileSystemAccessMode": {"enum": ["read", "write", "deny"], "type": "string"},
    "FileSystemPath": {
        "oneOf": [
            {
                "properties": {
                    "path": {"$ref": "#/definitions/LegacyAppPathString"},
                    "type": {"enum": ["path"], "type": "string"},
                },
                "required": ["path", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "pattern": {"type": "string"},
                    "type": {"enum": ["glob_pattern"], "type": "string"},
                },
                "required": ["pattern", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "type": {"enum": ["special"], "type": "string"},
                    "value": {"$ref": "#/definitions/FileSystemSpecialPath"},
                },
                "required": ["type", "value"],
                "type": "object",
            },
        ]
    },
    "FileSystemSandboxEntry": {
        "properties": {
            "access": {"$ref": "#/definitions/FileSystemAccessMode"},
            "path": {"$ref": "#/definitions/FileSystemPath"},
        },
        "required": ["access", "path"],
        "type": "object",
    },
    "FileSystemSpecialPath": {
        "oneOf": [
            {
                "properties": {"kind": {"enum": ["root"], "type": "string"}},
                "required": ["kind"],
                "type": "object",
            },
            {
                "properties": {"kind": {"enum": ["minimal"], "type": "string"}},
                "required": ["kind"],
                "type": "object",
            },
            {
                "properties": {
                    "kind": {"enum": ["project_roots"], "type": "string"},
                    "subpath": {
                        "anyOf": [
                            {"$ref": "#/definitions/LegacyAppPathString"},
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["kind"],
                "type": "object",
            },
            {
                "properties": {"kind": {"enum": ["tmpdir"], "type": "string"}},
                "required": ["kind"],
                "type": "object",
            },
            {
                "properties": {"kind": {"enum": ["slash_tmp"], "type": "string"}},
                "required": ["kind"],
                "type": "object",
            },
            {
                "properties": {
                    "kind": {"enum": ["unknown"], "type": "string"},
                    "path": {"type": "string"},
                    "subpath": {
                        "anyOf": [
                            {"$ref": "#/definitions/LegacyAppPathString"},
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["kind", "path"],
                "type": "object",
            },
        ]
    },
    "FileUpdateChange": {
        "properties": {
            "diff": {"type": "string"},
            "kind": {"$ref": "#/definitions/PatchChangeKind"},
            "path": {"type": "string"},
        },
        "required": ["diff", "kind", "path"],
        "type": "object",
    },
    "FunctionCallOutputBody": {
        "anyOf": [
            {"type": "string"},
            {
                "items": {"$ref": "#/definitions/FunctionCallOutputContentItem"},
                "type": "array",
            },
        ]
    },
    "FunctionCallOutputContentItem": {
        "oneOf": [
            {
                "properties": {
                    "text": {"type": "string"},
                    "type": {"enum": ["input_text"], "type": "string"},
                },
                "required": ["text", "type"],
                "type": "object",
            },
            {
                "anyOf": [
                    {
                        "properties": {"image_url": {"type": "string"}},
                        "required": ["image_url"],
                        "type": "object",
                    },
                    {
                        "properties": {"file_id": {"type": "string"}},
                        "required": ["file_id"],
                        "type": "object",
                    },
                ],
                "properties": {
                    "detail": {
                        "anyOf": [
                            {"$ref": "#/definitions/ImageDetail"},
                            {"type": "null"},
                        ]
                    },
                    "type": {"enum": ["input_image"], "type": "string"},
                },
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {
                    "audio_url": {"type": "string"},
                    "type": {"enum": ["input_audio"], "type": "string"},
                },
                "required": ["audio_url", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "encrypted_content": {"type": "string"},
                    "type": {"enum": ["encrypted_content"], "type": "string"},
                },
                "required": ["encrypted_content", "type"],
                "type": "object",
            },
        ]
    },
    "GuardianApprovalReview": {
        "properties": {
            "rationale": {"type": ["string", "null"]},
            "riskLevel": {
                "anyOf": [{"$ref": "#/definitions/GuardianRiskLevel"}, {"type": "null"}]
            },
            "status": {"$ref": "#/definitions/GuardianApprovalReviewStatus"},
            "userAuthorization": {
                "anyOf": [
                    {"$ref": "#/definitions/GuardianUserAuthorization"},
                    {"type": "null"},
                ]
            },
        },
        "required": ["status"],
        "type": "object",
    },
    "GuardianApprovalReviewAction": {
        "oneOf": [
            {
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"$ref": "#/definitions/LegacyAppPathString"},
                    "source": {"$ref": "#/definitions/GuardianCommandSource"},
                    "type": {"enum": ["command"], "type": "string"},
                },
                "required": ["command", "cwd", "source", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "argv": {"items": {"type": "string"}, "type": "array"},
                    "cwd": {"$ref": "#/definitions/AbsolutePathBuf"},
                    "program": {"type": "string"},
                    "source": {"$ref": "#/definitions/GuardianCommandSource"},
                    "type": {"enum": ["execve"], "type": "string"},
                },
                "required": ["argv", "cwd", "program", "source", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "approvalId": {"type": "string"},
                    "cwd": {"$ref": "#/definitions/LegacyAppPathString"},
                    "processId": {"type": "string"},
                    "stdin": {"type": "string"},
                    "type": {"enum": ["writeStdin"], "type": "string"},
                },
                "required": ["approvalId", "cwd", "processId", "stdin", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "cwd": {"$ref": "#/definitions/LegacyAppPathString"},
                    "files": {
                        "items": {"$ref": "#/definitions/LegacyAppPathString"},
                        "type": "array",
                    },
                    "type": {"enum": ["applyPatch"], "type": "string"},
                },
                "required": ["cwd", "files", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "host": {"type": "string"},
                    "port": {"minimum": 0.0, "type": "integer"},
                    "protocol": {"$ref": "#/definitions/NetworkApprovalProtocol"},
                    "target": {"type": "string"},
                    "type": {"enum": ["networkAccess"], "type": "string"},
                },
                "required": ["host", "port", "protocol", "target", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "connectorId": {"type": ["string", "null"]},
                    "connectorName": {"type": ["string", "null"]},
                    "server": {"type": "string"},
                    "toolName": {"type": "string"},
                    "toolTitle": {"type": ["string", "null"]},
                    "type": {"enum": ["mcpToolCall"], "type": "string"},
                },
                "required": ["server", "toolName", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "permissions": {"$ref": "#/definitions/RequestPermissionProfile"},
                    "reason": {"type": ["string", "null"]},
                    "type": {"enum": ["requestPermissions"], "type": "string"},
                },
                "required": ["permissions", "type"],
                "type": "object",
            },
        ]
    },
    "GuardianApprovalReviewStatus": {
        "enum": ["inProgress", "approved", "denied", "timedOut", "aborted"],
        "type": "string",
    },
    "GuardianCommandSource": {"enum": ["shell", "unifiedExec"], "type": "string"},
    "GuardianRiskLevel": {
        "enum": ["low", "medium", "high", "critical"],
        "type": "string",
    },
    "GuardianUserAuthorization": {
        "enum": ["unknown", "low", "medium", "high"],
        "type": "string",
    },
    "HookCompletedNotification": {
        "properties": {
            "run": {"$ref": "#/definitions/HookRunSummary"},
            "threadId": {"type": "string"},
            "turnId": {"type": ["string", "null"]},
        },
        "required": ["run", "threadId"],
        "type": "object",
    },
    "HookEventName": {
        "enum": [
            "preToolUse",
            "permissionRequest",
            "postToolUse",
            "preCompact",
            "postCompact",
            "sessionStart",
            "sessionEnd",
            "userPromptSubmit",
            "subagentStart",
            "subagentStop",
            "stop",
            "interrupt",
        ],
        "type": "string",
    },
    "HookExecutionMode": {"enum": ["sync", "async"], "type": "string"},
    "HookHandlerType": {
        "enum": ["command", "mcpTool", "prompt", "agent"],
        "type": "string",
    },
    "HookOutputEntry": {
        "properties": {
            "kind": {"$ref": "#/definitions/HookOutputEntryKind"},
            "text": {"type": "string"},
        },
        "required": ["kind", "text"],
        "type": "object",
    },
    "HookOutputEntryKind": {
        "enum": ["warning", "stop", "feedback", "context", "error"],
        "type": "string",
    },
    "HookPromptFragment": {
        "properties": {"hookRunId": {"type": "string"}, "text": {"type": "string"}},
        "required": ["hookRunId", "text"],
        "type": "object",
    },
    "HookRunStatus": {
        "enum": ["running", "completed", "failed", "blocked", "stopped"],
        "type": "string",
    },
    "HookRunSummary": {
        "properties": {
            "completedAt": {"type": ["integer", "null"]},
            "displayOrder": {"type": "integer"},
            "durationMs": {"type": ["integer", "null"]},
            "entries": {
                "items": {"$ref": "#/definitions/HookOutputEntry"},
                "type": "array",
            },
            "eventName": {"$ref": "#/definitions/HookEventName"},
            "executionMode": {"$ref": "#/definitions/HookExecutionMode"},
            "handlerType": {"$ref": "#/definitions/HookHandlerType"},
            "id": {"type": "string"},
            "scope": {"$ref": "#/definitions/HookScope"},
            "source": {"allOf": [{"$ref": "#/definitions/HookSource"}]},
            "sourcePath": {"$ref": "#/definitions/AbsolutePathBuf"},
            "startedAt": {"type": "integer"},
            "status": {"$ref": "#/definitions/HookRunStatus"},
            "statusMessage": {"type": ["string", "null"]},
        },
        "required": [
            "displayOrder",
            "entries",
            "eventName",
            "executionMode",
            "handlerType",
            "id",
            "scope",
            "sourcePath",
            "startedAt",
            "status",
        ],
        "type": "object",
    },
    "HookScope": {"enum": ["thread", "turn"], "type": "string"},
    "HookSource": {
        "enum": [
            "system",
            "user",
            "project",
            "mdm",
            "sessionFlags",
            "plugin",
            "cloudRequirements",
            "cloudManagedConfig",
            "legacyManagedConfigFile",
            "legacyManagedConfigMdm",
            "unknown",
        ],
        "type": "string",
    },
    "HookStartedNotification": {
        "properties": {
            "run": {"$ref": "#/definitions/HookRunSummary"},
            "threadId": {"type": "string"},
            "turnId": {"type": ["string", "null"]},
        },
        "required": ["run", "threadId"],
        "type": "object",
    },
    "ImageDetail": {"enum": ["auto", "low", "high", "original"], "type": "string"},
    "ImageGenerationFailure": {
        "oneOf": [
            {
                "properties": {
                    "limitId": {"type": "string"},
                    "resetsAt": {"type": ["integer", "null"]},
                    "type": {"enum": ["usageLimitExceeded"], "type": "string"},
                },
                "required": ["limitId", "type"],
                "type": "object",
            }
        ]
    },
    "ItemCompletedNotification": {
        "properties": {
            "completedAtMs": {"type": "integer"},
            "item": {"$ref": "#/definitions/ThreadItem"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["completedAtMs", "item", "threadId", "turnId"],
        "type": "object",
    },
    "ItemGuardianApprovalReviewCompletedNotification": {
        "properties": {
            "action": {"$ref": "#/definitions/GuardianApprovalReviewAction"},
            "completedAtMs": {"type": "integer"},
            "decisionSource": {"$ref": "#/definitions/AutoReviewDecisionSource"},
            "review": {"$ref": "#/definitions/GuardianApprovalReview"},
            "reviewId": {"type": "string"},
            "startedAtMs": {"type": "integer"},
            "targetItemId": {"type": ["string", "null"]},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": [
            "action",
            "completedAtMs",
            "decisionSource",
            "review",
            "reviewId",
            "startedAtMs",
            "threadId",
            "turnId",
        ],
        "type": "object",
    },
    "ItemGuardianApprovalReviewStartedNotification": {
        "properties": {
            "action": {"$ref": "#/definitions/GuardianApprovalReviewAction"},
            "review": {"$ref": "#/definitions/GuardianApprovalReview"},
            "reviewId": {"type": "string"},
            "startedAtMs": {"type": "integer"},
            "targetItemId": {"type": ["string", "null"]},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": [
            "action",
            "review",
            "reviewId",
            "startedAtMs",
            "threadId",
            "turnId",
        ],
        "type": "object",
    },
    "ItemStartedNotification": {
        "properties": {
            "item": {"$ref": "#/definitions/ThreadItem"},
            "startedAtMs": {"type": "integer"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["item", "startedAtMs", "threadId", "turnId"],
        "type": "object",
    },
    "LegacyAppPathString": {"type": "string"},
    "McpAppDisplayMode": {"enum": ["inline", "fullscreen"], "type": "string"},
    "McpAppUi": {
        "properties": {
            "preferredModelDisplayMode": {"$ref": "#/definitions/McpAppDisplayMode"},
            "resourceUri": {"type": "string"},
        },
        "required": ["preferredModelDisplayMode", "resourceUri"],
        "type": "object",
    },
    "McpToolCallAppContext": {
        "properties": {
            "actionName": {"type": ["string", "null"]},
            "appName": {"type": ["string", "null"]},
            "connectorId": {"type": "string"},
            "linkId": {"type": ["string", "null"]},
            "resourceUri": {"type": ["string", "null"]},
        },
        "required": ["connectorId"],
        "type": "object",
    },
    "McpToolCallError": {
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
        "type": "object",
    },
    "McpToolCallProgressNotification": {
        "properties": {
            "itemId": {"type": "string"},
            "message": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["itemId", "message", "threadId", "turnId"],
        "type": "object",
    },
    "McpToolCallResult": {
        "properties": {
            "_meta": True,
            "content": {"items": True, "type": "array"},
            "structuredContent": True,
        },
        "required": ["content"],
        "type": "object",
    },
    "McpToolCallStatus": {
        "enum": ["inProgress", "completed", "failed"],
        "type": "string",
    },
    "MemoryCitation": {
        "properties": {
            "entries": {
                "items": {"$ref": "#/definitions/MemoryCitationEntry"},
                "type": "array",
            },
            "threadIds": {"items": {"type": "string"}, "type": "array"},
        },
        "required": ["entries", "threadIds"],
        "type": "object",
    },
    "MemoryCitationEntry": {
        "properties": {
            "lineEnd": {"minimum": 0.0, "type": "integer"},
            "lineStart": {"minimum": 0.0, "type": "integer"},
            "note": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["lineEnd", "lineStart", "note", "path"],
        "type": "object",
    },
    "MessagePhase": {
        "oneOf": [
            {"enum": ["commentary"], "type": "string"},
            {"enum": ["final_answer"], "type": "string"},
        ]
    },
    "MisalignmentErrorDetails": {
        "properties": {
            "detailedExplanation": {"type": ["string", "null"]},
            "errorType": {"type": ["string", "null"]},
            "steer": {
                "anyOf": [{"$ref": "#/definitions/MisalignmentSteer"}, {"type": "null"}]
            },
        },
        "type": "object",
    },
    "MisalignmentSteer": {
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
        "type": "object",
    },
    "NetworkApprovalProtocol": {
        "enum": ["http", "https", "socks5Tcp", "socks5Udp"],
        "type": "string",
    },
    "NonSteerableTurnKind": {"enum": ["review", "compact"], "type": "string"},
    "PatchApplyStatus": {
        "enum": ["inProgress", "completed", "failed", "declined"],
        "type": "string",
    },
    "PatchChangeKind": {
        "oneOf": [
            {
                "properties": {"type": {"enum": ["add"], "type": "string"}},
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {"type": {"enum": ["delete"], "type": "string"}},
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {
                    "move_path": {"type": ["string", "null"]},
                    "type": {"enum": ["update"], "type": "string"},
                },
                "required": ["type"],
                "type": "object",
            },
        ]
    },
    "PlanDeltaNotification": {
        "properties": {
            "delta": {"type": "string"},
            "itemId": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["delta", "itemId", "threadId", "turnId"],
        "type": "object",
    },
    "ReasoningEffort": {"minLength": 1, "type": "string"},
    "ReasoningSummaryPartAddedNotification": {
        "properties": {
            "itemId": {"type": "string"},
            "summaryIndex": {"type": "integer"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["itemId", "summaryIndex", "threadId", "turnId"],
        "type": "object",
    },
    "ReasoningSummaryTextDeltaNotification": {
        "properties": {
            "delta": {"type": "string"},
            "itemId": {"type": "string"},
            "summaryIndex": {"type": "integer"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["delta", "itemId", "summaryIndex", "threadId", "turnId"],
        "type": "object",
    },
    "ReasoningTextDeltaNotification": {
        "properties": {
            "contentIndex": {"type": "integer"},
            "delta": {"type": "string"},
            "itemId": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["contentIndex", "delta", "itemId", "threadId", "turnId"],
        "type": "object",
    },
    "RequestPermissionProfile": {
        "additionalProperties": False,
        "properties": {
            "fileSystem": {
                "anyOf": [
                    {"$ref": "#/definitions/AdditionalFileSystemPermissions"},
                    {"type": "null"},
                ]
            },
            "network": {
                "anyOf": [
                    {"$ref": "#/definitions/AdditionalNetworkPermissions"},
                    {"type": "null"},
                ]
            },
        },
        "type": "object",
    },
    "StrictReviewRequiredNotification": {
        "properties": {
            "startedAtMs": {"type": "integer"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["startedAtMs", "threadId", "turnId"],
        "type": "object",
    },
    "SubAgentActivityKind": {
        "enum": ["started", "interacted", "interrupted", "completed"],
        "type": "string",
    },
    "TerminalInteractionNotification": {
        "properties": {
            "itemId": {"type": "string"},
            "processId": {"type": "string"},
            "stdin": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["itemId", "processId", "stdin", "threadId", "turnId"],
        "type": "object",
    },
    "TextElement": {
        "properties": {
            "byteRange": {"allOf": [{"$ref": "#/definitions/ByteRange"}]},
            "placeholder": {"type": ["string", "null"]},
        },
        "required": ["byteRange"],
        "type": "object",
    },
    "ThreadActiveFlag": {
        "enum": ["waitingOnApproval", "waitingOnUserInput"],
        "type": "string",
    },
    "ThreadItem": {
        "oneOf": [
            {
                "properties": {
                    "clientId": {"type": ["string", "null"]},
                    "content": {
                        "items": {"$ref": "#/definitions/UserInput"},
                        "type": "array",
                    },
                    "id": {"type": "string"},
                    "type": {"enum": ["userMessage"], "type": "string"},
                },
                "required": ["content", "id", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "fragments": {
                        "items": {"$ref": "#/definitions/HookPromptFragment"},
                        "type": "array",
                    },
                    "id": {"type": "string"},
                    "type": {"enum": ["hookPrompt"], "type": "string"},
                },
                "required": ["fragments", "id", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "delivery": {
                        "anyOf": [
                            {"$ref": "#/definitions/AgentMessageDelivery"},
                            {"type": "null"},
                        ]
                    },
                    "id": {"type": "string"},
                    "memoryCitation": {
                        "anyOf": [
                            {"$ref": "#/definitions/MemoryCitation"},
                            {"type": "null"},
                        ]
                    },
                    "phase": {
                        "anyOf": [
                            {"$ref": "#/definitions/MessagePhase"},
                            {"type": "null"},
                        ]
                    },
                    "questions": {
                        "items": {"$ref": "#/definitions/AsyncUserInputQuestion"},
                        "type": ["array", "null"],
                    },
                    "text": {"type": "string"},
                    "type": {"enum": ["agentMessage"], "type": "string"},
                },
                "required": ["id", "text", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "namespace": {"type": ["string", "null"]},
                    "output": {"$ref": "#/definitions/FunctionCallOutputBody"},
                    "type": {"enum": ["functionCallOutput"], "type": "string"},
                },
                "required": ["id", "name", "output", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "type": {"enum": ["plan"], "type": "string"},
                },
                "required": ["id", "text", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "content": {"items": {"type": "string"}, "type": "array"},
                    "id": {"type": "string"},
                    "summary": {"items": {"type": "string"}, "type": "array"},
                    "type": {"enum": ["reasoning"], "type": "string"},
                },
                "required": ["id", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "aggregatedOutput": {"type": ["string", "null"]},
                    "command": {"type": "string"},
                    "commandActions": {
                        "items": {"$ref": "#/definitions/CommandAction"},
                        "type": "array",
                    },
                    "cwd": {"allOf": [{"$ref": "#/definitions/LegacyAppPathString"}]},
                    "durationMs": {"type": ["integer", "null"]},
                    "exitCode": {"type": ["integer", "null"]},
                    "id": {"type": "string"},
                    "pluginId": {"type": ["string", "null"]},
                    "processId": {"type": ["string", "null"]},
                    "scriptPath": {"type": ["string", "null"]},
                    "source": {
                        "allOf": [{"$ref": "#/definitions/CommandExecutionSource"}]
                    },
                    "status": {"$ref": "#/definitions/CommandExecutionStatus"},
                    "type": {"enum": ["commandExecution"], "type": "string"},
                },
                "required": [
                    "command",
                    "commandActions",
                    "cwd",
                    "id",
                    "status",
                    "type",
                ],
                "type": "object",
            },
            {
                "properties": {
                    "changes": {
                        "items": {"$ref": "#/definitions/FileUpdateChange"},
                        "type": "array",
                    },
                    "id": {"type": "string"},
                    "status": {"$ref": "#/definitions/PatchApplyStatus"},
                    "type": {"enum": ["fileChange"], "type": "string"},
                },
                "required": ["changes", "id", "status", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "appContext": {
                        "anyOf": [
                            {"$ref": "#/definitions/McpToolCallAppContext"},
                            {"type": "null"},
                        ]
                    },
                    "arguments": True,
                    "durationMs": {"type": ["integer", "null"]},
                    "error": {
                        "anyOf": [
                            {"$ref": "#/definitions/McpToolCallError"},
                            {"type": "null"},
                        ]
                    },
                    "id": {"type": "string"},
                    "mcpAppResourceUri": {"type": ["string", "null"]},
                    "mcpAppUi": {
                        "anyOf": [{"$ref": "#/definitions/McpAppUi"}, {"type": "null"}]
                    },
                    "pluginId": {"type": ["string", "null"]},
                    "readOnlyHint": {"type": ["boolean", "null"]},
                    "result": {
                        "anyOf": [
                            {"$ref": "#/definitions/McpToolCallResult"},
                            {"type": "null"},
                        ]
                    },
                    "server": {"type": "string"},
                    "status": {"$ref": "#/definitions/McpToolCallStatus"},
                    "tool": {"type": "string"},
                    "type": {"enum": ["mcpToolCall"], "type": "string"},
                },
                "required": ["arguments", "id", "server", "status", "tool", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "arguments": True,
                    "contentItems": {
                        "items": {
                            "$ref": "#/definitions/DynamicToolCallOutputContentItem"
                        },
                        "type": ["array", "null"],
                    },
                    "durationMs": {"type": ["integer", "null"]},
                    "id": {"type": "string"},
                    "namespace": {"type": ["string", "null"]},
                    "status": {"$ref": "#/definitions/DynamicToolCallStatus"},
                    "success": {"type": ["boolean", "null"]},
                    "tool": {"type": "string"},
                    "type": {"enum": ["dynamicToolCall"], "type": "string"},
                },
                "required": ["arguments", "id", "status", "tool", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "agentsStates": {
                        "additionalProperties": {
                            "$ref": "#/definitions/CollabAgentState"
                        },
                        "type": "object",
                    },
                    "id": {"type": "string"},
                    "model": {"type": ["string", "null"]},
                    "prompt": {"type": ["string", "null"]},
                    "reasoningEffort": {
                        "anyOf": [
                            {"$ref": "#/definitions/ReasoningEffort"},
                            {"type": "null"},
                        ]
                    },
                    "receiverThreadIds": {"items": {"type": "string"}, "type": "array"},
                    "senderThreadId": {"type": "string"},
                    "status": {
                        "allOf": [{"$ref": "#/definitions/CollabAgentToolCallStatus"}]
                    },
                    "tool": {"allOf": [{"$ref": "#/definitions/CollabAgentTool"}]},
                    "type": {"enum": ["collabAgentToolCall"], "type": "string"},
                },
                "required": [
                    "agentsStates",
                    "id",
                    "receiverThreadIds",
                    "senderThreadId",
                    "status",
                    "tool",
                    "type",
                ],
                "type": "object",
            },
            {
                "properties": {
                    "agentPath": {"type": "string"},
                    "agentThreadId": {"type": "string"},
                    "id": {"type": "string"},
                    "kind": {"$ref": "#/definitions/SubAgentActivityKind"},
                    "type": {"enum": ["subAgentActivity"], "type": "string"},
                },
                "required": ["agentPath", "agentThreadId", "id", "kind", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "action": {
                        "anyOf": [
                            {"$ref": "#/definitions/WebSearchAction"},
                            {"type": "null"},
                        ]
                    },
                    "id": {"type": "string"},
                    "query": {"type": "string"},
                    "results": {"items": True, "type": ["array", "null"]},
                    "type": {"enum": ["webSearch"], "type": "string"},
                },
                "required": ["id", "query", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "id": {"type": "string"},
                    "path": {"$ref": "#/definitions/LegacyAppPathString"},
                    "type": {"enum": ["imageView"], "type": "string"},
                },
                "required": ["id", "path", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "durationMs": {"minimum": 0.0, "type": "integer"},
                    "id": {"type": "string"},
                    "type": {"enum": ["sleep"], "type": "string"},
                },
                "required": ["durationMs", "id", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "failure": {
                        "anyOf": [
                            {"$ref": "#/definitions/ImageGenerationFailure"},
                            {"type": "null"},
                        ]
                    },
                    "id": {"type": "string"},
                    "result": {"type": "string"},
                    "revisedPrompt": {"type": ["string", "null"]},
                    "savedPath": {
                        "anyOf": [
                            {"$ref": "#/definitions/AbsolutePathBuf"},
                            {"type": "null"},
                        ]
                    },
                    "status": {"type": "string"},
                    "transparentBackground": {"type": ["boolean", "null"]},
                    "type": {"enum": ["imageGeneration"], "type": "string"},
                },
                "required": ["id", "result", "status", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "id": {"type": "string"},
                    "review": {"type": "string"},
                    "type": {"enum": ["enteredReviewMode"], "type": "string"},
                },
                "required": ["id", "review", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "id": {"type": "string"},
                    "review": {"type": "string"},
                    "type": {"enum": ["exitedReviewMode"], "type": "string"},
                },
                "required": ["id", "review", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "id": {"type": "string"},
                    "type": {"enum": ["contextCompaction"], "type": "string"},
                },
                "required": ["id", "type"],
                "type": "object",
            },
        ]
    },
    "ThreadStatus": {
        "oneOf": [
            {
                "properties": {"type": {"enum": ["notLoaded"], "type": "string"}},
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {"type": {"enum": ["idle"], "type": "string"}},
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {"type": {"enum": ["systemError"], "type": "string"}},
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {
                    "activeFlags": {
                        "items": {"$ref": "#/definitions/ThreadActiveFlag"},
                        "type": "array",
                    },
                    "type": {"enum": ["active"], "type": "string"},
                },
                "required": ["activeFlags", "type"],
                "type": "object",
            },
        ]
    },
    "ThreadStatusChangedNotification": {
        "properties": {
            "status": {"$ref": "#/definitions/ThreadStatus"},
            "threadId": {"type": "string"},
        },
        "required": ["status", "threadId"],
        "type": "object",
    },
    "ThreadTokenUsage": {
        "properties": {
            "last": {"$ref": "#/definitions/TokenUsageBreakdown"},
            "modelContextWindow": {"type": ["integer", "null"]},
            "total": {"$ref": "#/definitions/TokenUsageBreakdown"},
        },
        "required": ["last", "total"],
        "type": "object",
    },
    "ThreadTokenUsageUpdatedNotification": {
        "properties": {
            "threadId": {"type": "string"},
            "tokenUsage": {"$ref": "#/definitions/ThreadTokenUsage"},
            "turnId": {"type": "string"},
        },
        "required": ["threadId", "tokenUsage", "turnId"],
        "type": "object",
    },
    "TokenUsageBreakdown": {
        "properties": {
            "cacheWriteInputTokens": {"type": "integer"},
            "cachedInputTokens": {"type": "integer"},
            "inputTokens": {"type": "integer"},
            "outputTokens": {"type": "integer"},
            "reasoningOutputTokens": {"type": "integer"},
            "totalTokens": {"type": "integer"},
        },
        "required": [
            "cachedInputTokens",
            "inputTokens",
            "outputTokens",
            "reasoningOutputTokens",
            "totalTokens",
        ],
        "type": "object",
    },
    "Turn": {
        "properties": {
            "completedAt": {"type": ["integer", "null"]},
            "durationMs": {"type": ["integer", "null"]},
            "error": {"anyOf": [{"$ref": "#/definitions/TurnError"}, {"type": "null"}]},
            "id": {"type": "string"},
            "items": {"items": {"$ref": "#/definitions/ThreadItem"}, "type": "array"},
            "itemsView": {"allOf": [{"$ref": "#/definitions/TurnItemsView"}]},
            "startedAt": {"type": ["integer", "null"]},
            "status": {"$ref": "#/definitions/TurnStatus"},
        },
        "required": ["id", "items", "status"],
        "type": "object",
    },
    "TurnCompletedNotification": {
        "properties": {
            "threadId": {"type": "string"},
            "turn": {"$ref": "#/definitions/Turn"},
        },
        "required": ["threadId", "turn"],
        "type": "object",
    },
    "TurnDiffUpdatedNotification": {
        "properties": {
            "diff": {"type": "string"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["diff", "threadId", "turnId"],
        "type": "object",
    },
    "TurnError": {
        "properties": {
            "additionalDetails": {"type": ["string", "null"]},
            "codexErrorInfo": {
                "anyOf": [{"$ref": "#/definitions/CodexErrorInfo"}, {"type": "null"}]
            },
            "message": {"type": "string"},
            "misalignment": {
                "anyOf": [
                    {"$ref": "#/definitions/MisalignmentErrorDetails"},
                    {"type": "null"},
                ]
            },
        },
        "required": ["message"],
        "type": "object",
    },
    "TurnItemsView": {
        "oneOf": [
            {"enum": ["notLoaded"], "type": "string"},
            {"enum": ["summary"], "type": "string"},
            {"enum": ["full"], "type": "string"},
        ]
    },
    "TurnPlanStep": {
        "properties": {
            "status": {"$ref": "#/definitions/TurnPlanStepStatus"},
            "step": {"type": "string"},
        },
        "required": ["status", "step"],
        "type": "object",
    },
    "TurnPlanStepStatus": {
        "enum": ["pending", "inProgress", "completed"],
        "type": "string",
    },
    "TurnPlanUpdatedNotification": {
        "properties": {
            "explanation": {"type": ["string", "null"]},
            "plan": {"items": {"$ref": "#/definitions/TurnPlanStep"}, "type": "array"},
            "threadId": {"type": "string"},
            "turnId": {"type": "string"},
        },
        "required": ["plan", "threadId", "turnId"],
        "type": "object",
    },
    "TurnStartedNotification": {
        "properties": {
            "threadId": {"type": "string"},
            "turn": {"$ref": "#/definitions/Turn"},
        },
        "required": ["threadId", "turn"],
        "type": "object",
    },
    "TurnStatus": {
        "enum": ["completed", "interrupted", "failed", "inProgress"],
        "type": "string",
    },
    "UserInput": {
        "oneOf": [
            {
                "properties": {
                    "text": {"type": "string"},
                    "text_elements": {
                        "items": {"$ref": "#/definitions/TextElement"},
                        "type": "array",
                    },
                    "type": {"enum": ["text"], "type": "string"},
                },
                "required": ["text", "type"],
                "type": "object",
            },
            {
                "anyOf": [
                    {
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                        "type": "object",
                    },
                    {
                        "properties": {"fileId": {"type": "string"}},
                        "required": ["fileId"],
                        "type": "object",
                    },
                ],
                "properties": {
                    "detail": {
                        "anyOf": [
                            {"$ref": "#/definitions/ImageDetail"},
                            {"type": "null"},
                        ]
                    },
                    "type": {"enum": ["image"], "type": "string"},
                },
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {
                    "detail": {
                        "anyOf": [
                            {"$ref": "#/definitions/ImageDetail"},
                            {"type": "null"},
                        ]
                    },
                    "path": {"type": "string"},
                    "type": {"enum": ["localImage"], "type": "string"},
                },
                "required": ["path", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "type": {"enum": ["audio"], "type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["type", "url"],
                "type": "object",
            },
            {
                "properties": {
                    "path": {"type": "string"},
                    "type": {"enum": ["localAudio"], "type": "string"},
                },
                "required": ["path", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                    "type": {"enum": ["skill"], "type": "string"},
                },
                "required": ["name", "path", "type"],
                "type": "object",
            },
            {
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                    "type": {"enum": ["mention"], "type": "string"},
                },
                "required": ["name", "path", "type"],
                "type": "object",
            },
        ]
    },
    "WebSearchAction": {
        "oneOf": [
            {
                "properties": {
                    "queries": {"items": {"type": "string"}, "type": ["array", "null"]},
                    "query": {"type": ["string", "null"]},
                    "type": {"enum": ["search"], "type": "string"},
                },
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {
                    "type": {"enum": ["openPage"], "type": "string"},
                    "url": {"type": ["string", "null"]},
                },
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {
                    "pattern": {"type": ["string", "null"]},
                    "type": {"enum": ["findInPage"], "type": "string"},
                    "url": {"type": ["string", "null"]},
                },
                "required": ["type"],
                "type": "object",
            },
            {
                "properties": {"type": {"enum": ["other"], "type": "string"}},
                "required": ["type"],
                "type": "object",
            },
        ]
    },
}


def _matches(value, schema, budget, depth=0):
    budget[0] -= 1
    if budget[0] < 0 or depth > 64:
        raise ValueError("Managed observation schema budget exceeded")
    if schema is True:
        return True
    if schema is False:
        return False
    if "$ref" in schema:
        return _matches(
            value, DEFINITIONS[schema["$ref"].rsplit("/", 1)[1]], budget, depth + 1
        )
    for key in ("allOf", "anyOf", "oneOf"):
        if key in schema:
            results = [
                _matches(value, child, budget, depth + 1) for child in schema[key]
            ]
            if not (
                all(results)
                if key == "allOf"
                else any(results)
                if key == "anyOf"
                else sum(results) == 1
            ):
                return False
    if "enum" in schema and not any(
        type(value) is type(v) and value == v for v in schema["enum"]
    ):
        return False
    kinds = schema.get("type", [])
    if isinstance(kinds, str):
        kinds = [kinds]
    checks = {
        "null": value is None,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "number": type(value) in (int, float),
    }
    if kinds and not any(checks[k] for k in kinds):
        return False
    if (
        type(value) in (int, float)
        and "minimum" in schema
        and value < schema["minimum"]
    ):
        return False
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        return False
    if isinstance(value, list) and "items" in schema:
        return all(_matches(v, schema["items"], budget, depth + 1) for v in value)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if not set(schema.get("required", [])) <= value.keys():
            return False
        # Closed declared structures; explicit map/JSON-value schemas retain
        # their vendor-defined additional properties, bounded by native_codec.
        additional = schema.get(
            "additionalProperties", False if "properties" in schema else True
        )
        for key, v in value.items():
            if key in props:
                if not _matches(v, props[key], budget, depth + 1):
                    return False
            elif not _matches(v, additional, budget, depth + 1):
                return False
    return True


def validate(message, thread_id, turn_id=None):
    from native_codex import _bounded

    _bounded(message)
    if (
        not isinstance(message, dict)
        or set(message) - {"method", "params", "jsonrpc"}
        or message.get("jsonrpc", "2.0") != "2.0"
    ):
        raise ValueError("Managed observation is not a native notification")
    method = message.get("method")
    if (
        not isinstance(method, str)
        or method not in SCHEMAS
        or not _matches(message.get("params"), SCHEMAS[method], [100000])
    ):
        raise ValueError(
            "Unknown or malformed managed native notification: " + str(method)
        )
    p = message["params"]
    if p.get("threadId") != thread_id:
        raise ValueError("Managed native notification belongs to another thread")
    observed = p.get("turnId")
    if method in ("turn/started", "turn/completed"):
        observed = p["turn"]["id"]
    if turn_id is not None and observed is not None and observed != turn_id:
        raise ValueError("Managed native notification belongs to another turn")
    return p


def transcript(rows, thread_id, turn_id):
    """Require one completed foreground turn and every emitted item/hook pair.

    This checks captured native continuity only. Permission enforcement is
    separately qualified by the canonical probe and its admitted transport.
    """
    from native_callback import CallbackIncomplete

    started = False
    terminal = None
    items = {}
    closed = set()
    completed_items = {}
    hooks = {}
    closed_hooks = set()
    for row in rows:
        method = row.get("method")
        if method is None or method == "thread/started":
            continue
        p = validate(row, thread_id, turn_id)
        if method.startswith("hook/"):
            run = p["run"]
            identity = run["id"]
            if run["eventName"] == "sessionStart":
                if p.get("turnId") is not None or run["scope"] != "thread":
                    raise ValueError("SessionStart scope differs")
            elif run["scope"] == "turn" and p.get("turnId") != turn_id:
                raise ValueError("Productive hook has no current turn binding")
            if method == "hook/started":
                if (
                    identity in hooks
                    or identity in closed_hooks
                    or run["status"] != "running"
                    or run.get("completedAt") is not None
                    or run["entries"]
                ):
                    raise ValueError("Ambiguous hook start")
                hooks[identity] = run
            else:
                old = hooks.pop(identity, None)
                if (
                    old is None
                    or identity in closed_hooks
                    or any(
                        run[k] != old[k]
                        for k in (
                            "id",
                            "eventName",
                            "sourcePath",
                            "scope",
                            "source",
                            "executionMode",
                            "handlerType",
                            "startedAt",
                            "displayOrder",
                        )
                    )
                ):
                    raise ValueError("Unpaired or changed productive hook")
                if (
                    run["status"] != "completed"
                    or type(run.get("completedAt")) is not int
                    or run["completedAt"] < run["startedAt"]
                    or any(e["kind"] in ("error", "stop") for e in run["entries"])
                ):
                    raise ValueError("Observed native hook refused or failed")
                closed_hooks.add(identity)
            continue
        if method == "thread/status/changed":
            if p["status"]["type"] == "systemError":
                raise ValueError("Native session reported system error")
            continue
        if method == "turn/started":
            if started or terminal or p["turn"]["status"] != "inProgress":
                raise ValueError("Ambiguous productive turn start")
            started = True
            continue
        if method == "turn/completed":
            if (
                not started
                or terminal is not None
                or p["turn"]["status"] == "inProgress"
            ):
                raise ValueError("Ambiguous productive turn terminal")
            if p["turn"].get("itemsView", "full") != "full":
                raise ValueError("Native turn items are only partially observed")
            if (
                p["turn"]["status"] == "completed"
                and p["turn"].get("error") is not None
            ):
                raise ValueError("Successful native turn contradicts its error")
            snapshot_ids = set()
            for item in p["turn"]["items"]:
                identity = item["id"]
                if identity in snapshot_ids or completed_items.get(identity) != item:
                    raise ValueError(
                        "Native terminal item is unseen, duplicated or changed"
                    )
                snapshot_ids.add(identity)
            terminal = p["turn"]
            continue
        if not started or terminal is not None:
            # Token snapshots can arrive immediately after a completed turn;
            # typed turn identity still binds them, they do not close work.
            if method != "thread/tokenUsage/updated":
                raise ValueError("Productive item outside active native turn")
        if method in ("item/started", "item/completed"):
            item = p["item"]
            identity = item["id"]
            if method == "item/started":
                if identity in items or identity in closed:
                    raise ValueError("Duplicated native item")
                items[identity] = item["type"]
            else:
                if items.pop(identity, None) != item["type"] or identity in closed:
                    raise ValueError("Unpaired native item completion")
                if item.get("status") == "inProgress":
                    raise ValueError("Native completed item is still in progress")
                completed_items[identity] = item
                closed.add(identity)
        elif "itemId" in p and p["itemId"] not in items:
            raise ValueError("Native item update has no active owned item")
        if method == "error" and not p["willRetry"]:
            raise ValueError("Native productive execution reported a terminal error")
    if terminal is None or items or hooks:
        raise CallbackIncomplete(
            "Native productive turn or emitted item/hook coverage is incomplete"
        )
    if terminal["status"] not in ("completed", "failed", "interrupted"):
        raise ValueError("Unsupported native turn terminal status")
    return terminal
