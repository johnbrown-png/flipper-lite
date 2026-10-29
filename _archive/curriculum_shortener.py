"""
Curriculum Description Shortener
Compresses verbose educational statements from ~140 to ~50 words using GPT-4
For matching video transcript chunks in semantic search system.
"""

import pandas as pd
import os
from openai import OpenAI
from datetime import datetime
import random
from typing import List, Dict, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class CurriculumShortener:
    def __init__(self, csv_path: str, api_key: str = None):
        """
        Initialize the curriculum shortener.
        
        Args:
            csv_path: Path to the curriculum CSV file
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        
        # Columns containing descriptions
        self.desc_columns = ['SS1_desc', 'SS2_desc', 'SS3_desc', 'SS4_desc', 
                             'SS5_desc', 'SS6_desc', 'SS7_desc']
        
        print(f"✓ Loaded CSV: {len(self.df)} rows")
        print(f"✓ Found {len(self.desc_columns)} description columns")
    
    def get_all_descriptions(self) -> List[Tuple[int, str, str]]:
        """
        Extract all non-empty descriptions from the CSV.
        
        Returns:
            List of tuples (row_index, column_name, description_text)
        """
        descriptions = []
        for idx, row in self.df.iterrows():
            for col in self.desc_columns:
                desc = row[col]
                if pd.notna(desc) and str(desc).strip():
                    descriptions.append((idx, col, str(desc).strip()))
        return descriptions
    
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
    
    def shorten_description(self, description: str) -> Dict[str, any]:
        """
        Send description to GPT-4 for compression.
        
        Returns:
            Dictionary with original, shortened, word counts, and cost
        """
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
            
            # Calculate token usage and cost
            total_tokens = response.usage.total_tokens
            cost = (total_tokens / 1000) * 0.03  # GPT-4 pricing
            
            return {
                'original': description,
                'shortened': shortened,
                'original_words': len(description.split()),
                'shortened_words': len(shortened.split()),
                'tokens_used': total_tokens,
                'cost_usd': cost,
                'success': True
            }
        
        except Exception as e:
            return {
                'original': description,
                'shortened': None,
                'error': str(e),
                'success': False
            }
    
    def run_trial(self, num_samples: int = 5) -> List[Dict]:
        """
        Run trial on random sample of descriptions.
        
        Args:
            num_samples: Number of random samples to test (default: 5)
            
        Returns:
            List of result dictionaries
        """
        print(f"\n{'='*80}")
        print(f"TRIAL RUN - Random {num_samples} samples")
        print(f"{'='*80}\n")
        
        # Get all descriptions
        all_descriptions = self.get_all_descriptions()
        print(f"✓ Found {len(all_descriptions)} non-empty descriptions")
        
        # Random sample
        samples = random.sample(all_descriptions, min(num_samples, len(all_descriptions)))
        
        results = []
        total_cost = 0
        
        for i, (row_idx, col_name, description) in enumerate(samples, 1):
            unique_row = self.df.iloc[row_idx]['UniqueRow']
            
            print(f"\n{'-'*80}")
            print(f"SAMPLE {i}/{len(samples)}")
            print(f"Row: {unique_row}")
            print(f"Column: {col_name}")
            print(f"{'-'*80}")
            
            print(f"\nORIGINAL ({len(description.split())} words):")
            print(f"{description[:200]}..." if len(description) > 200 else description)
            
            print(f"\n⏳ Processing...")
            
            result = self.shorten_description(description)
            result['row_index'] = row_idx
            result['column_name'] = col_name
            result['unique_row'] = unique_row
            
            if result['success']:
                print(f"\n✓ SHORTENED ({result['shortened_words']} words):")
                print(result['shortened'])
                print(f"\n💰 Cost: ${result['cost_usd']:.4f} | Tokens: {result['tokens_used']}")
                total_cost += result['cost_usd']
            else:
                print(f"\n✗ ERROR: {result['error']}")
            
            results.append(result)
        
        # Summary
        print(f"\n{'='*80}")
        print(f"TRIAL SUMMARY")
        print(f"{'='*80}")
        print(f"Samples processed: {len(results)}")
        print(f"Successful: {sum(1 for r in results if r['success'])}")
        print(f"Failed: {sum(1 for r in results if not r['success'])}")
        print(f"Total cost: ${total_cost:.4f}")
        
        if results and results[0]['success']:
            avg_original = sum(r['original_words'] for r in results if r['success']) / len([r for r in results if r['success']])
            avg_shortened = sum(r['shortened_words'] for r in results if r['success']) / len([r for r in results if r['success']])
            print(f"Avg original length: {avg_original:.1f} words")
            print(f"Avg shortened length: {avg_shortened:.1f} words")
            print(f"Compression ratio: {(avg_shortened/avg_original)*100:.1f}%")
        
        # Estimate full run cost
        total_descriptions = len(all_descriptions)
        estimated_cost = (total_cost / len(results)) * total_descriptions
        print(f"\n💡 ESTIMATED FULL RUN ({total_descriptions} descriptions): ${estimated_cost:.2f}")
        
        return results
    
    def run_full_batch(self, output_path: str = None, prompt_version: str = "v1") -> pd.DataFrame:
        """
        Process all descriptions and create output CSV with shortened columns.
        
        Args:
            output_path: Path for output CSV (auto-generated if None)
            prompt_version: Version identifier for tracking prompt iterations
            
        Returns:
            DataFrame with original + shortened columns
        """
        print(f"\n{'='*80}")
        print(f"FULL BATCH RUN")
        print(f"{'='*80}\n")
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.csv_path.replace('.csv', f'_shortened_{timestamp}.csv')
        
        # Create a copy of the dataframe
        output_df = self.df.copy()
        
        # Add shortened columns
        for col in self.desc_columns:
            output_df[f"{col}_short"] = None
        
        # Get all descriptions to process
        all_descriptions = self.get_all_descriptions()
        total = len(all_descriptions)
        
        print(f"Processing {total} descriptions...")
        print(f"Output will be saved to: {output_path}\n")
        
        total_cost = 0
        successful = 0
        failed = 0
        
        for i, (row_idx, col_name, description) in enumerate(all_descriptions, 1):
            unique_row = self.df.iloc[row_idx]['UniqueRow']
            
            print(f"[{i}/{total}] {unique_row} - {col_name}... ", end='', flush=True)
            
            result = self.shorten_description(description)
            
            if result['success']:
                output_df.at[row_idx, f"{col_name}_short"] = result['shortened']
                total_cost += result['cost_usd']
                successful += 1
                print(f"✓ ({result['shortened_words']} words, ${result['cost_usd']:.4f})")
            else:
                failed += 1
                print(f"✗ ERROR: {result.get('error', 'Unknown error')}")
            
            # Save progress every 50 rows
            if i % 50 == 0:
                output_df.to_csv(output_path, index=False)
                print(f"  💾 Progress saved ({i}/{total})")
        
        # Final save
        output_df.to_csv(output_path, index=False)
        
        # Summary
        print(f"\n{'='*80}")
        print(f"BATCH COMPLETE")
        print(f"{'='*80}")
        print(f"Total processed: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total cost: ${total_cost:.2f}")
        print(f"Output saved to: {output_path}")
        print(f"{'='*80}\n")
        
        return output_df


def main():
    """Run trial mode by default."""
    import sys
    
    csv_path = r"c:\Users\johnf\OneDrive\Documents\Visual Studio Code\flipper16012026\Curriculum\Maths\mat_curr_import - 02032026.csv"
    
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found at {csv_path}")
        return
    
    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please add it to your .env file or set it as an environment variable")
        return
    
    shortener = CurriculumShortener(csv_path)
    
    # Default to trial mode
    if len(sys.argv) > 1 and sys.argv[1] == '--full':
        print("\n⚠️  FULL BATCH MODE - This will process all descriptions and incur API costs")
        confirm = input("Are you sure you want to continue? (yes/no): ")
        if confirm.lower() == 'yes':
            shortener.run_full_batch()
        else:
            print("Cancelled.")
    else:
        print("\n🧪 TRIAL MODE - Testing with 5 random samples")
        print("To run full batch, use: python curriculum_shortener.py --full\n")
        shortener.run_trial(num_samples=5)


if __name__ == "__main__":
    main()
