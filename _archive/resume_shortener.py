"""
Resume Curriculum Description Shortener
Picks up where the previous run stopped due to quota limits
"""

import pandas as pd
import os
from openai import OpenAI
from datetime import datetime
from typing import List, Tuple
from dotenv import load_dotenv
import time

load_dotenv()

class ResumeShortener:
    def __init__(self, partial_csv_path: str, api_key: str = None):
        """
        Initialize with the partially completed CSV.
        
        Args:
            partial_csv_path: Path to the CSV with some shortened descriptions
            api_key: OpenAI API key
        """
        self.csv_path = partial_csv_path
        self.df = pd.read_csv(partial_csv_path)
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        
        self.desc_columns = ['SS1_desc', 'SS2_desc', 'SS3_desc', 'SS4_desc', 
                             'SS5_desc', 'SS6_desc', 'SS7_desc']
        
        print(f"✓ Loaded partial CSV: {len(self.df)} rows")
        
    def get_remaining_descriptions(self) -> List[Tuple[int, str, str]]:
        """
        Find descriptions that still need processing.
        
        Returns:
            List of tuples (row_index, column_name, description_text)
        """
        remaining = []
        for idx, row in self.df.iterrows():
            for col in self.desc_columns:
                short_col = f"{col}_short"
                
                # Check if original has content but shortened is empty
                original_desc = row[col]
                shortened_desc = row[short_col]
                
                if pd.notna(original_desc) and str(original_desc).strip():
                    if pd.isna(shortened_desc) or not str(shortened_desc).strip():
                        remaining.append((idx, col, str(original_desc).strip()))
        
        return remaining
    
    def get_prompt(self, description: str) -> str:
        """Generate the compression prompt for GPT-4."""
        return f"""Task: Condense this UK maths curriculum statement from ~140 to ~50 words.

Context: This text will be used to match relevant video transcript chunks in a semantic search system.

Requirements:
- Remove filler words, repetitions, and verbose explanations
- Simplify complex language to accessible terms that would appear in educational videos
- Preserve core learning objectives and key mathematical concepts
- Keep searchable keywords (e.g., "number bonds", "partition", "ten frame")
- Maintain clarity for educators and search relevance
- Target exactly 50 words (±5 words acceptable)

Original text ({len(description.split())} words):
{description}

Condensed version (target 50 words):"""
    
    def shorten_description(self, description: str) -> dict:
        """Send description to GPT-4 for compression."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at condensing educational text while preserving meaning and search relevance."},
                    {"role": "user", "content": self.get_prompt(description)}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            shortened = response.choices[0].message.content.strip()
            total_tokens = response.usage.total_tokens
            cost = (total_tokens / 1000) * 0.03
            
            return {
                'shortened': shortened,
                'shortened_words': len(shortened.split()),
                'tokens_used': total_tokens,
                'cost_usd': cost,
                'success': True,
                'error': None
            }
        
        except Exception as e:
            error_msg = str(e)
            # Check if it's a quota error
            is_quota_error = '429' in error_msg or 'quota' in error_msg.lower()
            
            return {
                'shortened': None,
                'error': error_msg,
                'success': False,
                'is_quota_error': is_quota_error
            }
    
    def resume_processing(self, output_path: str = None) -> dict:
        """
        Resume processing from where it stopped.
        
        Returns:
            Dictionary with completion stats
        """
        print(f"\n{'='*80}")
        print(f"RESUMING BATCH PROCESSING")
        print(f"{'='*80}\n")
        
        # Get remaining work
        remaining = self.get_remaining_descriptions()
        total_remaining = len(remaining)
        
        if total_remaining == 0:
            print("✅ All descriptions already processed!")
            return {'completed': True, 'already_done': True}
        
        print(f"Found {total_remaining} descriptions still to process")
        print(f"Estimated cost: ${(total_remaining * 0.011):.2f}")
        print(f"Estimated time: {(total_remaining * 2 / 60):.1f} minutes\n")
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.csv_path.replace('.csv', f'_resumed_{timestamp}.csv')
        
        # Work on a copy
        output_df = self.df.copy()
        
        total_cost = 0
        successful = 0
        failed = 0
        quota_exceeded = False
        last_processed_idx = None
        
        for i, (row_idx, col_name, description) in enumerate(remaining, 1):
            unique_row = self.df.iloc[row_idx]['UniqueRow']
            
            print(f"[{i}/{total_remaining}] {unique_row} - {col_name}... ", end='', flush=True)
            
            result = self.shorten_description(description)
            
            if result['success']:
                output_df.at[row_idx, f"{col_name}_short"] = result['shortened']
                total_cost += result['cost_usd']
                successful += 1
                last_processed_idx = i
                print(f"✓ ({result['shortened_words']} words, ${result['cost_usd']:.4f})")
            else:
                failed += 1
                
                # Check if quota error
                if result.get('is_quota_error', False):
                    quota_exceeded = True
                    print(f"⚠️  QUOTA EXCEEDED")
                    print(f"\n{'='*80}")
                    print(f"⚠️  API QUOTA LIMIT REACHED AGAIN")
                    print(f"{'='*80}")
                    print(f"Processed: {successful}/{total_remaining}")
                    print(f"Remaining: {total_remaining - i}")
                    print(f"Last successful: {unique_row}")
                    print(f"{'='*80}\n")
                    break
                else:
                    print(f"✗ ERROR: {result['error'][:50]}...")
            
            # Save progress every 50 descriptions
            if i % 50 == 0:
                output_df.to_csv(output_path, index=False)
                print(f"  💾 Progress saved ({i}/{total_remaining})")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
        
        # Final save
        output_df.to_csv(output_path, index=False)
        
        # Summary
        print(f"\n{'='*80}")
        if quota_exceeded:
            print(f"⚠️  PROCESSING STOPPED - QUOTA EXCEEDED")
        else:
            print(f"✅ BATCH COMPLETE")
        print(f"{'='*80}")
        print(f"Attempted: {successful + failed}/{total_remaining}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Cost this run: ${total_cost:.2f}")
        print(f"Output saved: {output_path}")
        
        if quota_exceeded:
            print(f"\n⚠️  You'll need to add more credits and run again to complete.")
            print(f"   Remaining: {total_remaining - (successful + failed)} descriptions")
        else:
            print(f"\n✅ ALL DESCRIPTIONS SUCCESSFULLY PROCESSED!")
        
        print(f"{'='*80}\n")
        
        return {
            'completed': not quota_exceeded,
            'successful': successful,
            'failed': failed,
            'total_cost': total_cost,
            'quota_exceeded': quota_exceeded,
            'output_path': output_path
        }


def main():
    """Resume processing."""
    
    # Find the most recent partial output
    partial_csv = r"c:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\Curriculum\Maths\mat_curr_import - 02032026_shortened_20260303_160628_resumed_20260303_174758.csv"
    
    if not os.path.exists(partial_csv):
        print(f"❌ Error: Partial CSV not found at {partial_csv}")
        return
    
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        return
    
    print("\n🔄 RESUMING CURRICULUM SHORTENER")
    print("This will continue from where the previous run stopped\n")
    
    shortener = ResumeShortener(partial_csv)
    result = shortener.resume_processing()
    
    if result['completed'] and not result.get('already_done'):
        print("\n🎉 SUCCESS! All 1,488 descriptions have been shortened.")
        print(f"📁 Final output: {result['output_path']}")
    elif result.get('quota_exceeded'):
        print("\n⚠️  ALERT: Processing stopped due to quota limit.")
        print("Please add more credits to OpenAI and run this script again.")
    elif result.get('already_done'):
        print("\n✅ Nothing to do - all descriptions already processed!")


if __name__ == "__main__":
    main()
