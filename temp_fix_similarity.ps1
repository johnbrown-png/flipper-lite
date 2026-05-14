$ErrorActionPreference = 'Stop'

function Slugify([string]$text) {
  $s = $text.ToLowerInvariant()
  $s = $s -replace '[^a-z0-9\s-]', ''
  $s = $s -replace '\s+', '-'
  $s = $s.Trim('-')
  return $s
}

$currPath = 'Curriculum/Maths/curriculum_08052026_small_steps.csv'
$preA = 'precomputed_recommendations_flat.csv'
$preB = 'precomputed_recommendations_flat'
$conPath = 'Improve_pick/constraints_gate.csv'

$curr = Import-Csv $currPath -Encoding UTF8

# Find base rows for Year 9 Spring Similarity currently at 1135..1137
$simRows = $curr | Where-Object {
  $_.year -eq 'Year 9' -and $_.term -eq 'Spring' -and $_.macro_topic -eq 'Similarity' -and [int]$_.small_step_num -ge 1135 -and [int]$_.small_step_num -le 1137
} | Sort-Object { [int]$_.small_step_num }

if ($simRows.Count -ne 3) {
  throw "Expected exactly 3 Similarity rows at 1135..1137, found $($simRows.Count)."
}

# Shift global numbering down-stream by +1 to make room for inserted step at 1138
foreach ($r in $curr) {
  if ([int]$r.small_step_num -ge 1138) {
    $r.small_step_num = ([int]$r.small_step_num + 1).ToString()
  }
}

$names = @(
  'Recognise enlargement and similarity',
  'Work out unknown lengths and angles in similar shapes',
  'Solve problems with similar triangles E',
  'Ratio in right-angled triangles E'
)

$ratioWrDesc = 'In this extend step, before the formal study of trigonometry later in the year, students explore the ratios of side lengths in right-angled triangles, building on their previous understanding of ratios in similar triangles.Define and explain the terms “hypotenuse”, “adjacent” and “opposite”. Start with right-angled triangles with interior anglesof 30° and 60°. Encourage students to label the sides correctlyand then to explore the relationships between these sides asdecimals, fractions or ratios. They should compare the ratioswith similar triangles, discussing the patterns that they observe. They use the ratios to calculate unknown side lengths and angles in similar triangles. Once students are confident,they could extend their exploration to ratios in other right-angled triangles.'

# Re-map existing 1135..1137 rows (preserve ss_wr_desc/ss_desc by row position)
for ($i = 0; $i -lt 3; $i++) {
  $r = $simRows[$i]
  $step = $i + 1
  $r.unique_row = 'Year9SpringSimilarity'
  $r.topic = 'Similarity'
  $r.small_step_num = (1135 + $i).ToString()
  $r.small_step_num_in_topic = $step.ToString()
  $r.legacy_step_position = $step.ToString()
  $r.small_step_name = $names[$i]
  $r.small_step_id = "Year 9_13-14_Spring__Similarity_$step_$($r.small_step_name)"
  $r.small_step_key = "year-9__13-14__spring__blank__similarity__$step__$(Slugify $r.small_step_name)"
}

# Insert new step 4 at 1138
$clone = [pscustomobject]@{}
foreach ($p in $simRows[2].PSObject.Properties.Name) {
  $clone | Add-Member -NotePropertyName $p -NotePropertyValue $simRows[2].$p
}
$clone.unique_row = 'Year9SpringSimilarity'
$clone.topic = 'Similarity'
$clone.small_step_num = '1138'
$clone.small_step_num_in_topic = '4'
$clone.legacy_step_position = '4'
$clone.small_step_name = $names[3]
$clone.ss_wr_desc = $ratioWrDesc
$clone.ss_desc = 'Students explore side-length ratios in right-angled triangles before formal trigonometry, using hypotenuse, adjacent and opposite to solve unknowns.'
$clone.small_step_id = "Year 9_13-14_Spring__Similarity_4_$($clone.small_step_name)"
$clone.small_step_key = "year-9__13-14__spring__blank__similarity__4__$(Slugify $clone.small_step_name)"

# Place inserted row immediately after 1137
$out = New-Object System.Collections.Generic.List[object]
$inserted = $false
foreach ($r in $curr) {
  $out.Add($r)
  if (-not $inserted -and [int]$r.small_step_num -eq 1137 -and $r.year -eq 'Year 9' -and $r.term -eq 'Spring' -and $r.macro_topic -eq 'Similarity') {
    $out.Add($clone)
    $inserted = $true
  }
}
if (-not $inserted) { throw 'Failed to insert new 1138 Similarity row.' }

$out | Export-Csv $currPath -NoTypeInformation -Encoding UTF8

# Canonical map from updated curriculum 1135..1138
$currUpdated = Import-Csv $currPath -Encoding UTF8
$canonRows = $currUpdated | Where-Object { [int]$_.small_step_num -ge 1135 -and [int]$_.small_step_num -le 1138 -and $_.year -eq 'Year 9' -and $_.term -eq 'Spring' -and $_.macro_topic -eq 'Similarity' } | Sort-Object { [int]$_.small_step_num }
if ($canonRows.Count -ne 4) { throw "Expected 4 canonical curriculum rows, found $($canonRows.Count)." }
$canon = @{}
foreach ($r in $canonRows) { $canon[[int]$r.small_step_num] = $r }

function Sync-Precomputed([string]$path) {
  $pc = Import-Csv $path -Encoding UTF8
  foreach ($r in $pc) {
    $g = 0
    if ([int]::TryParse($r.small_step_num_global, [ref]$g)) {
      if ($canon.ContainsKey($g)) {
        $c = $canon[$g]
        $r.topic = 'Similarity'
        $r.small_step_num = $c.small_step_num_in_topic
        $r.small_step_num_in_topic = $c.small_step_num_in_topic
        $r.small_step = $c.small_step_name
        $r.small_step_name = $c.small_step_name
        $r.small_step_desc = $c.ss_wr_desc
        $r.ss_wr_desc = $c.ss_wr_desc
        $r.small_step_id = $c.small_step_id
        $r.small_step_key = $c.small_step_key
        $n = 0
        if ([int]::TryParse($r.recommendation_num, [ref]$n)) {
          $r.recommendation_id = "$($c.small_step_id)_recommendation_$n"
        }
      }
    }
  }
  $pc | Export-Csv $path -NoTypeInformation -Encoding UTF8
}

Sync-Precomputed $preA
Sync-Precomputed $preB

# Update constraints gate rows for this block
$con = Import-Csv $conPath -Encoding UTF8
$conFiltered = $con | Where-Object {
  -not (
    $_.small_step_id -like 'Year 9_13-14_Spring__Recognise enlargement and similarity_*' -or
    $_.small_step_id -like 'Year 9_13-14_Spring__Similarity_*'
  )
}
$newCon = foreach ($c in $canonRows) {
  [pscustomobject]@{
    small_step_id = $c.small_step_id
    not_aligned = '0'
    ss_wr_desc = $c.ss_wr_desc
    objective_core_one_sentence_about_what_the_pupil_must_be_doinglearning_now = ''
    must_include_signals_termsactions_that_should_appear = ''
    'must_not_include_signals_adjacent-topic_drift_terms_for_example_capacity_focus_when_the_stepis_mass-only' = ''
    'numericadomain_bounds_explict_limits_for_example:_numbers_up_to_10_only,_no_values_above_10_unless_the_objective_says_so' = ''
    Reject_rule_if_any_hard_violation,_fail_gate. = ''
  }
}
@($conFiltered + $newCon) | Export-Csv $conPath -NoTypeInformation -Encoding UTF8

# Verification output
"=== Curriculum 1135..1140 ==="
Import-Csv $currPath -Encoding UTF8 |
  Where-Object { [int]$_.small_step_num -ge 1135 -and [int]$_.small_step_num -le 1140 } |
  Select-Object small_step_num,small_step_num_in_topic,topic,small_step_name,small_step_id |
  Format-Table -AutoSize

"=== Precomputed A distinct 1135..1138 ==="
Import-Csv $preA -Encoding UTF8 |
  Where-Object { [int]$_.small_step_num_global -ge 1135 -and [int]$_.small_step_num_global -le 1138 } |
  Select-Object small_step_num_global,topic,small_step_num,small_step_name,small_step_id |
  Sort-Object {[int]$_.small_step_num_global}, {[int]$_.small_step_num} |
  Select-Object -Unique |
  Format-Table -AutoSize

"=== Precomputed B distinct 1135..1138 ==="
Import-Csv $preB -Encoding UTF8 |
  Where-Object { [int]$_.small_step_num_global -ge 1135 -and [int]$_.small_step_num_global -le 1138 } |
  Select-Object small_step_num_global,topic,small_step_num,small_step_name,small_step_id |
  Sort-Object {[int]$_.small_step_num_global}, {[int]$_.small_step_num} |
  Select-Object -Unique |
  Format-Table -AutoSize

"=== Constraints Similarity rows ==="
Import-Csv $conPath -Encoding UTF8 |
  Where-Object { $_.small_step_id -like 'Year 9_13-14_Spring__Similarity_*' } |
  Select-Object small_step_id,not_aligned |
  Format-Table -AutoSize
