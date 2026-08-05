class Embedder:
    def __init__(self, type='pairing', max_len=1800):
        if type not in ['pairing', 'roster', 'standing']:
            raise ValueError("Report type must be ['pairing', 'roaster', 'standing'].")
        self.type = type
        self.max_len = max_len

    def chunk_lines(self, lines: list[str], max_len: int = 1800) -> list[str]:
        chunks = []
        current_chunk = []
        current_length = 0

        for line in lines:
            # Length of line + 1 character for the newline separator "\n"
            line_len = len(line) + (1 if current_chunk else 0)

            # If adding this line exceeds max_len, wrap up the current chunk
            if current_length + line_len > max_len and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0

            current_chunk.append(line)
            current_length += len(line) + (1 if len(current_chunk) > 1 else 0)

        # Append any remaining lines
        if current_chunk:
            chunks.append("\n".join(current_chunk) + "\n")

        return chunks

    # def build_table(self, headers, rows):
    #     col_widths = [len(h) for h in headers]
    #     for player in rows:
    #         for i, val in enumerate(player):
    #             display_val = val.strip()
    #             col_widths[i] = max(col_widths[i], len(display_val))

    #     table_rows = []
        
    #     # Build header row
    #     header_line = " | ".join(
    #         h.ljust(col_widths[i]) for i, h in enumerate(headers)
    #     )
    #     separator = "-+-".join("-" * col_widths[i] for i in range(len(headers)))

    #     table_rows.append(header_line)
    #     table_rows.append(separator)

    #     # Build data rows
    #     for player in rows:
    #         formatted_row = " | ".join(
    #             val.strip().ljust(col_widths[i])
    #             for i, val in enumerate(player)
    #         )
    #         table_rows.append(formatted_row)

    #     table_chunks = self.chunk_lines(table_rows)
    #         # f"{header_line}\n{separator}\n" + "\n".join(data_lines) + "\n\n"


    #     return table_chunks


    def build(self, report):
        if self.type == 'pairing':
            pass

        elif self.type == 'roster':
            messages = {}
            for div, players in report.items():
                messages[div] = {}
                number_players = len(players)
                div_title = f"🏆 **{div} Division Roster -- {number_players} Players:**"
                messages[div]['title'] = div_title
                messages[div]['content'] = self.chunk_lines(players)
            return messages

        elif self.type == 'standing':
            pass