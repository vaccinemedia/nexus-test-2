; photofit6.asm — bank 6 at #C000: the interrogation portrait. Composes the
; selected features into a line buffer and a silhouette buffer, turns those
; into Spectrum cells, and keeps the result so later redraws are a copy.
; Entered via photofit.asm.
;
; Cell scheme (one ink + one paper per 8x8 cell):
;   inside the silhouette   black lines on skin- or hair-coloured paper
;   on its edge             skin- or hair-coloured ink on black, pixels =
;                           silhouette minus lines, which rounds the outline
;   outside                 black
; The four eye cells are always inside, so the interrogation can recolour
; them through pf_eye_attr exactly as it did the old block portrait.

    MODULE pf6
    ORG #C000

; Draws the portrait, building it first if this subject's face is new.
draw:
    ld a, (pf_built)
    or a
    call z, build
    ld hl, ink
    ld de, PF_PORTRAIT_SCR
    ld b, PF_SH
.line:
    push bc
    push de
    ld bc, PF_SW
    ldir
    pop de
    call next_line
    pop bc
    djnz .line
    ld hl, attrs
    ld de, ATTR_BASE + PORTRAIT_ROW * 32 + PORTRAIT_COL
    ld a, PF_SH / 8
.arow:
    ld bc, PF_SW
    ldir
    ex de, hl
    ld bc, 32 - PF_SW
    add hl, bc
    ex de, hl
    dec a
    jr nz, .arow
    ret

; DE = screen address -> same column on the next pixel line
next_line:
    inc d
    ld a, d
    and 7
    ret nz
    ld a, e
    add a, 32
    ld e, a
    ret c
    ld a, d
    sub 8
    ld d, a
    ret

; ---------------------------------------------------------------------------
build:
    ld hl, ink
    ld de, ink + 1
    ld bc, PF_SBUF * 2 - 1          ; ink and sil are adjacent
    ld (hl), 0
    ldir
    ld a, (pf_sel + PF_HEAD)
    ld hl, pfs_head_tab
    call feature
    call head_silhouette
    ld a, (pf_sel + PF_COLLAR)
    ld hl, pfs_collar_tab
    call feature
    ld a, (pf_sel + PF_MARKS)
    call is_glasses
    jr c, .no_marks
    ld a, (pf_sel + PF_MARKS)
    ld hl, pfs_marks_tab
    call feature
.no_marks:
    ld a, (pf_sel + PF_EYES)
    ld hl, pfs_eyes_tab
    call feature
    ld a, (pf_sel + PF_BROWS)
    ld hl, pfs_brows_tab
    call feature
    ld a, (pf_sel + PF_NOSE)
    ld hl, pfs_nose_tab
    call feature
    ld a, (pf_sel + PF_MOUTH)
    ld hl, pfs_mouth_tab
    call feature
    ld a, (pf_sel + PF_FACIAL)
    ld hl, pfs_facial_tab
    call feature
    ld a, (pf_sel + PF_HAIR)
    ld hl, pfs_hair_tab
    call feature
    ld a, (pf_sel + PF_MARKS)
    call is_glasses
    jr nc, .cells
    ld a, (pf_sel + PF_MARKS)
    ld hl, pfs_marks_tab
    call feature
.cells:
    call cells
    ld a, 1
    ld (pf_built), a
    ret

; Carry set if A is a glasses mark (variants 1 and 2), drawn over the hair.
is_glasses:
    dec a
    cp 2
    ret

; A = variant, HL = category table: ink &= ~mask, sil |= mask, ink |= lines
feature:
    add a, a
    add a, a
    ld e, a
    ld d, 0
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    ld a, (hl)
    inc hl
    ld h, (hl)
    ld l, a
    push hl
    push de
    ex de, hl
    ld de, ink
    call dec_andnot
    pop hl
    ld de, sil
    call dec_or
    pop hl
    ld de, ink

; HL = stream, DE = buffer: buffer |= stream
dec_or:
    ld a, (hl)
    inc hl
    or a
    ret z
    cp #C0
    jr nc, .ones
    cp #80
    jr nc, .skip
    ld b, a
.lit:
    ld a, (de)
    or (hl)
    ld (de), a
    inc hl
    inc de
    djnz .lit
    jr dec_or
.ones:
    sub #BF
    ld b, a
    ld a, #FF
.one:
    ld (de), a
    inc de
    djnz .one
    jr dec_or
.skip:
    sub #7F
    add a, e
    ld e, a
    jr nc, dec_or
    inc d
    jr dec_or

; HL = stream, DE = buffer: buffer &= ~stream
dec_andnot:
    ld a, (hl)
    inc hl
    or a
    ret z
    cp #C0
    jr nc, .zeros
    cp #80
    jr nc, .skip
    ld b, a
.lit:
    ld a, (hl)
    cpl
    ex de, hl
    and (hl)
    ld (hl), a
    ex de, hl
    inc hl
    inc de
    djnz .lit
    jr dec_andnot
.zeros:
    sub #BF
    ld b, a
    xor a
.zero:
    ld (de), a
    inc de
    djnz .zero
    jr dec_andnot
.skip:
    sub #7F
    add a, e
    ld e, a
    jr nc, dec_andnot
    inc d
    jr dec_andnot

; ---------------------------------------------------------------------------
; The head's silhouette isn't stored: fill each row of the head outline
; between its leftmost and rightmost pixel (tools/photofit span_fill).
head_silhouette:
    ld hl, ink
    ld b, PF_SH
.row:
    push bc
    push hl
    ld b, 0
.find_left:
    ld a, (hl)
    or a
    jr nz, .got_left
    inc hl
    inc b
    bit 3, b
    jr z, .find_left
    jr .done                        ; empty row
.got_left:
    ld c, a                         ; smear right: every bit from the first set one
    srl a
    or c
    ld c, a
    srl a
    srl a
    or c
    ld c, a
    rrca
    rrca
    rrca
    rrca
    and #0F
    or c
    ld (left_mask), a
    ld a, b
    ld (left_idx), a
    pop hl
    push hl
    ld de, PF_SW - 1
    add hl, de
    ld b, PF_SW - 1
.find_right:
    ld a, (hl)
    or a
    jr nz, .got_right
    dec hl
    dec b
    jr .find_right
.got_right:
    ld c, a                         ; smear left: every bit up to the last set one
    add a, a
    or c
    ld c, a
    add a, a
    add a, a
    or c
    ld c, a
    rlca
    rlca
    rlca
    rlca
    and #F0
    or c
    ld c, a                         ; C = right mask, B = right index
    pop hl
    push hl
    ld de, PF_SBUF
    add hl, de
    ld a, (left_idx)
    ld e, a
    ld d, 0
    add hl, de                      ; HL = sil byte at the left index
    ld d, a                         ; D = current index
.fill:
    ld e, #FF
    ld a, (left_idx)
    cp d
    jr nz, .not_left
    ld a, (left_mask)
    ld e, a
.not_left:
    ld a, d
    cp b
    jr nz, .not_right
    ld a, e
    and c
    ld e, a
.not_right:
    ld a, (hl)
    or e
    ld (hl), a
    inc hl
    ld a, d
    cp b
    jr z, .done
    inc d
    jr .fill
.done:
    pop hl
    ld de, PF_SW
    add hl, de
    pop bc
    djnz .row
    ret

; ---------------------------------------------------------------------------
; Turns ink + sil into finished cell pixels (in place in ink) and attrs.
cells:
    ld a, (pf_skin)
    add a, a
    ld e, a
    ld d, 0
    ld hl, skin_attrs
    add hl, de
    ld a, (hl)
    ld (skin_in), a
    ld (pf_eye_attr), a
    inc hl
    ld a, (hl)
    ld (skin_edge), a
    ld a, (pf_hairc)
    add a, a
    ld e, a
    ld hl, hair_attrs
    add hl, de
    ld a, (hl)
    ld (hair_in), a
    inc hl
    ld a, (hl)
    ld (hair_edge), a
    ld a, (pf_sel + PF_HAIR)
    ld hl, pfs_hair_cells
    call map_ptr
    ld (hair_map), hl
    ld a, (pf_sel + PF_FACIAL)
    ld hl, pfs_facial_cells
    call map_ptr
    ld (facial_map), hl
    ld a, (pf_sel + PF_FACIAL)
    ld e, a
    ld d, 0
    ld hl, pf_mouth_hidden
    add hl, de
    ld a, (hl)
    ld (mouth_off), a

    ld hl, ink
    ld ix, attrs
    xor a
    ld (row), a
.row:
    ld de, (hair_map)               ; hair-coloured cells on this row
    ld a, (de)
    inc de
    ld (hair_map), de
    ld b, a
    ld de, (facial_map)
    ld a, (de)
    inc de
    ld (facial_map), de
    or b
    ld (hbits), a
    xor a
    ld (col), a
.col:
    push hl                         ; D = AND, E = OR of the cell's sil bytes
    ld de, PF_SBUF
    add hl, de
    ld de, #FF00
    ld b, 8
.scan:
    ld a, (hl)
    ld c, a
    and d
    ld d, a
    ld a, c
    or e
    ld e, a
    ld a, l
    add a, PF_SW
    ld l, a
    jr nc, .scan_next
    inc h
.scan_next:
    djnz .scan
    pop hl
    ld a, (hbits)
    add a, a
    ld (hbits), a
    ld bc, (skin_in)                ; C = inside attr, B = edge attr
    jr nc, .colour
    ld bc, (hair_in)
.colour:
    ld a, e
    or a
    jr z, .outside
    ld a, d
    inc a
    jr z, .inside

    ld (ix + 0), b                  ; edge
    push hl
    ld de, PF_SBUF
    ld b, 8
.edge:
    ld a, (hl)
    cpl
    ld c, a
    push hl
    add hl, de
    ld a, (hl)
    pop hl
    and c
    ld (hl), a
    ld a, l
    add a, PF_SW
    ld l, a
    jr nc, .edge_next
    inc h
.edge_next:
    djnz .edge
    pop hl
    jr .next

.outside:
    ld (ix + 0), 0
    push hl
    ld b, 8
.clear:
    ld (hl), 0
    ld a, l
    add a, PF_SW
    ld l, a
    jr nc, .clear_next
    inc h
.clear_next:
    djnz .clear
    pop hl
    jr .next

.inside:
    ld a, (row)                     ; the mouth's lines are red
    cp PF_MOUTH_ROW
    jr nz, .plain
    ld a, (col)
    sub PF_MOUTH_COL
    cp 2
    jr nc, .plain
    ld a, (mouth_off)
    or a
    jr nz, .plain
    ld a, (skin_in)
    cp c
    jr nz, .plain
    or INK_RED
    ld c, a
.plain:
    ld (ix + 0), c

.next:
    inc hl
    inc ix
    ld a, (col)
    inc a
    ld (col), a
    cp PF_SW
    jp nz, .col
    ld de, PF_SW * 7
    add hl, de
    ld a, (row)
    inc a
    ld (row), a
    cp PF_SH / 8
    jp nz, .row
    ret

; HL = table + A * 12
map_ptr:
    push hl
    ld l, a
    ld h, 0
    add hl, hl
    ld e, l
    ld d, h
    add hl, hl
    add hl, de
    add hl, hl
    pop de
    add hl, de
    ret

; Inside (paper) and edge (ink) attributes for each skin and hair colour.
skin_attrs:
    DB INK_WHITE*8 + BRIGHT,  INK_WHITE + BRIGHT
    DB INK_YELLOW*8 + BRIGHT, INK_YELLOW + BRIGHT
    DB INK_CYAN*8 + BRIGHT,   INK_CYAN + BRIGHT
    DB INK_WHITE*8,           INK_WHITE
hair_attrs:
    DB INK_BLUE*8 + BRIGHT,   INK_BLUE + BRIGHT
    DB INK_RED*8 + BRIGHT,    INK_RED + BRIGHT
    DB INK_MAG*8 + BRIGHT,    INK_MAG + BRIGHT
    DB INK_GREEN*8 + BRIGHT,  INK_GREEN + BRIGHT

skin_in:    DB 0                    ; skin_in/skin_edge and hair_in/hair_edge
skin_edge:  DB 0                    ; are read as pairs with ld bc, (nn)
hair_in:    DB 0
hair_edge:  DB 0
hair_map:   DW 0
facial_map: DW 0
mouth_off:  DB 0
hbits:      DB 0
row:        DB 0
col:        DB 0
left_idx:   DB 0
left_mask:  DB 0

    INCLUDE "photofit_small.inc"
End:

; Work buffers live after the loaded data and are never saved to tape.
ink     EQU End                     ; lines, then finished cell pixels
sil     EQU ink + PF_SBUF
attrs   EQU sil + PF_SBUF
    ASSERT attrs + PF_SH / 8 * PF_SW <= #10000, "photofit bank 6 is full"
    ENDMODULE
