#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SERVER_NAME "aiws-cowork-mcp-smoke"
#define PROTOCOL_VERSION "2024-11-05"

static int is_json_whitespace(char value) {
    return value == ' ' || value == '\t' || value == '\n' || value == '\r';
}

static int find_json_value_internal(const char *json, const char *key, char *value, size_t value_size, int preserve_quotes) {
    char pattern[64];
    const char *cursor;
    const char *start;
    const char *end;
    const char *copy_start;
    const char *copy_end;
    size_t length;

    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    cursor = strstr(json, pattern);
    if (cursor == NULL) {
        return 0;
    }

    cursor = strchr(cursor + strlen(pattern), ':');
    if (cursor == NULL) {
        return 0;
    }
    cursor++;
    while (is_json_whitespace(*cursor)) {
        cursor++;
    }

    if (*cursor == '"') {
        start = cursor + 1;
        end = start;
        while (*end != '\0' && *end != '"') {
            if (*end == '\\' && end[1] != '\0') {
                end += 2;
            } else {
                end++;
            }
        }
        if (*end != '"') {
            return 0;
        }
    } else {
        start = cursor;
        end = start;
        while (*end != '\0' && *end != ',' && *end != '}' && *end != '\n' && *end != '\r') {
            end++;
        }
        while (end > start && is_json_whitespace(end[-1])) {
            end--;
        }
    }

    if (preserve_quotes && *cursor == '"') {
        copy_start = cursor;
        copy_end = end + 1;
    } else {
        copy_start = start;
        copy_end = end;
    }

    length = (size_t)(copy_end - copy_start);
    if (value_size == 0) {
        return 0;
    }
    if (length >= value_size) {
        length = value_size - 1;
    }
    memcpy(value, copy_start, length);
    value[length] = '\0';
    return 1;
}

static int find_json_value(const char *json, const char *key, char *value, size_t value_size) {
    return find_json_value_internal(json, key, value, value_size, 0);
}

static int find_json_raw_value(const char *json, const char *key, char *value, size_t value_size) {
    return find_json_value_internal(json, key, value, value_size, 1);
}

static void write_response(const char *id, const char *result_json) {
    printf("{\"jsonrpc\":\"2.0\",\"id\":%s,\"result\":%s}\n", id, result_json);
    fflush(stdout);
}

static void write_error(const char *id, int code, const char *message) {
    printf("{\"jsonrpc\":\"2.0\",\"id\":%s,\"error\":{\"code\":%d,\"message\":\"%s\"}}\n", id, code, message);
    fflush(stdout);
}

static int has_tool_name(const char *json) {
    char name[256];

    return find_json_value(json, "name", name, sizeof(name)) &&
           strcmp(name, "aiws.smoke.ping") == 0;
}

static void handle_message(const char *line) {
    char id[256];
    char method[256];
    char protocol_version[256];
    int has_id = find_json_raw_value(line, "id", id, sizeof(id));
    int has_method = find_json_value(line, "method", method, sizeof(method));

    if (!has_method) {
        return;
    }

    if (strcmp(method, "notifications/initialized") == 0) {
        return;
    }

    if (!has_id || id[0] == '\0') {
        return;
    }

    if (strcmp(method, "initialize") == 0) {
        char result[768];
        if (!find_json_value(line, "protocolVersion", protocol_version, sizeof(protocol_version))) {
            snprintf(protocol_version, sizeof(protocol_version), "%s", PROTOCOL_VERSION);
        }
        snprintf(
            result,
            sizeof(result),
            "{\"protocolVersion\":\"%s\",\"capabilities\":{\"tools\":{\"listChanged\":false}},\"serverInfo\":{\"name\":\"" SERVER_NAME "\",\"version\":\"0.1.0\"}}",
            protocol_version);
        write_response(id, result);
        return;
    }

    if (strcmp(method, "tools/list") == 0) {
        write_response(
            id,
            "{\"tools\":[{\"name\":\"aiws.smoke.ping\",\"description\":\"Return a deterministic AIWS Cowork MCP smoke response.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false}}]}");
        return;
    }

    if (strcmp(method, "tools/call") == 0) {
        if (has_tool_name(line)) {
            write_response(
                id,
                "{\"content\":[{\"type\":\"text\",\"text\":\"aiws-cowork-mcp-smoke pong\"}],\"isError\":false}");
        } else {
            write_error(id, -32602, "Unknown smoke tool");
        }
        return;
    }

    write_error(id, -32601, "Method not found");
}

int main(int argc, char **argv) {
    char line[8192];

    if (argc == 2 && strcmp(argv[1], "--self-test") == 0) {
        puts("aiws-cowork-mcp-smoke self-test ok");
        return 0;
    }

    while (fgets(line, sizeof(line), stdin) != NULL) {
        handle_message(line);
    }

    return 0;
}
