from typing import Dict, List, Any
from datetime import datetime, timedelta
import time
import database


class RiskScorer:
    """Calculate fraud risk score based on multiple signals"""
    
    def __init__(self):
        self.max_score = 100
        self.risk_levels = {
            "low": (0, 30),
            "medium": (30, 60),
            "high": (60, 85),
            "critical": (85, 101)
        }
    
    def calculate_risk_score(
        self,
        fingerprint: str,
        email: str,
        metadata: Dict[str, Any],
        file_name: str
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive risk score based on 5 layers
        """
        score = 0
        signals = []
        risk_factors = {}
        
        # Layer 1: Device Fingerprint Analysis
        fp_score, fp_signals, fp_factors = self._analyze_fingerprint(fingerprint)
        score += fp_score
        signals.extend(fp_signals)
        risk_factors.update({f"fingerprint_{k}": v for k, v in fp_factors.items()})
        
        # Layer 2: Document Metadata Forensics
        meta_score, meta_signals, meta_factors = self._analyze_metadata(metadata, fingerprint)
        score += meta_score
        signals.extend(meta_signals)
        risk_factors.update({f"metadata_{k}": v for k, v in meta_factors.items()})
        
        # Layer 3: Behavioral Patterns
        behav_score, behav_signals, behav_factors = self._analyze_behavior(
            fingerprint, email, file_name
        )
        score += behav_score
        signals.extend(behav_signals)
        risk_factors.update({f"behavior_{k}": v for k, v in behav_factors.items()})
        
        # Layer 4: Writing Style (if text available)
        style_score, style_signals, style_factors = self._analyze_writing_style(metadata)
        score += style_score
        signals.extend(style_signals)
        risk_factors.update({f"style_{k}": v for k, v in style_factors.items()})
        
        # Layer 5: Content Similarity
        content_score, content_signals, content_factors = self._analyze_content(
            metadata, fingerprint
        )
        score += content_score
        signals.extend(content_signals)
        risk_factors.update({f"content_{k}": v for k, v in content_factors.items()})
        
        # Cap the score at 100
        final_score = min(int(score), 100)
        
        # Determine risk level
        risk_level = self._get_risk_level(final_score)
        
        # Get linked accounts
        linked_info = database.link_accounts(fingerprint, [email])
        
        return {
            "risk_score": final_score,
            "risk_level": risk_level,
            "signals": signals,
            "risk_factors": risk_factors,
            "linked_accounts": linked_info.get("linked_accounts", []),
            "account_count": linked_info.get("account_count", 1),
            "recommendation": self._get_recommendation(final_score, signals)
        }
    
    def _analyze_fingerprint(self, fingerprint: str) -> tuple:
        """Layer 1: Device Fingerprint Analysis"""
        score = 0
        signals = []
        factors = {}
        
        # Check if this fingerprint has been seen before
        matching_subs = database.get_submissions_by_fingerprint(fingerprint)
        
        if len(matching_subs) == 0:
            signals.append("✓ New device fingerprint")
            factors["first_submission"] = True
            score += 0
        elif len(matching_subs) == 1:
            signals.append("• Device seen before (1 prior account)")
            factors["prior_accounts"] = 1
            score += 5
        elif len(matching_subs) <= 3:
            signals.append(f"⚠ Device fingerprint matches {len(matching_subs)} prior accounts")
            factors["prior_accounts"] = len(matching_subs)
            score += 30
        else:
            signals.append(f"🔴 Device fingerprint matches {len(matching_subs)} prior accounts")
            factors["prior_accounts"] = len(matching_subs)
            score += 40
        
        factors["fingerprint_matches"] = len(matching_subs)
        
        return score, signals, factors
    
    def _analyze_metadata(self, metadata: Dict[str, Any], fingerprint: str) -> tuple:
        """Layer 2: Document Metadata Forensics"""
        score = 0
        signals = []
        factors = {}
        
        if metadata.get("error"):
            return 0, [], {}
        
        author = metadata.get("author", "")
        creator = metadata.get("creator", "")
        
        # Check for author/creator metadata
        if author:
            similar_docs = database.get_author_metadata_matches(author, creator)
            if len(similar_docs) > 1:
                score += 20
                signals.append(f"⚠ Document author '{author}' found in {len(similar_docs)} submissions")
                factors["author_matches"] = len(similar_docs)
        
        # Check for creator/software match
        if creator:
            creator_matches = [
                s for s in database.get_submissions_by_fingerprint(fingerprint)
                if s.get("metadata", {}).get("creator") == creator
            ]
            if len(creator_matches) > 1:
                score += 15
                signals.append(f"• Same document editor: {creator}")
                factors["creator_matches"] = len(creator_matches)
        
        # Check file size consistency (might indicate templates)
        file_size = metadata.get("file_size", 0)
        if file_size > 0:
            similar_sizes = [
                s for s in database.get_submissions_by_fingerprint(fingerprint)
                if abs(s.get("metadata", {}).get("file_size", 0) - file_size) < file_size * 0.1
            ]
            if len(similar_sizes) > 2:
                score += 10
                signals.append("• Similar file sizes (possible template reuse)")
                factors["size_pattern"] = len(similar_sizes)
        
        # Check for suspiciously old creation dates
        creation_date = metadata.get("creation_date", "")
        if creation_date and ("1970" in creation_date or "1980" in creation_date):
            score += 5
            signals.append("• Suspicious creation date (possible metadata manipulation)")
            factors["date_manipulation"] = True
        
        factors["metadata_score"] = score
        return score, signals, factors
    
    def _analyze_behavior(
        self, fingerprint: str, email: str, file_name: str
    ) -> tuple:
        """Layer 3: Behavioral Patterns"""
        score = 0
        signals = []
        factors = {}
        
        # Check upload velocity
        recent_subs = database.get_recent_submissions(minutes=10)
        fingerprint_velocity = len(
            [s for s in recent_subs if s.get("fingerprint") == fingerprint]
        )
        
        if fingerprint_velocity >= 5:
            score += 35
            signals.append(f"🔴 BULK UPLOAD: {fingerprint_velocity} files in 10 minutes")
            factors["bulk_upload"] = fingerprint_velocity
        elif fingerprint_velocity >= 3:
            score += 25
            signals.append(f"⚠ Multiple uploads: {fingerprint_velocity} files in 10 minutes")
            factors["rapid_upload"] = fingerprint_velocity
        elif fingerprint_velocity >= 2:
            score += 10
            signals.append(f"• {fingerprint_velocity} uploads in short timeframe")
            factors["multiple_uploads"] = fingerprint_velocity

        email_submissions = database.get_submissions_by_email(email)
        if len(email_submissions) > 1:
            score += 5
            signals.append(f"• Email seen in {len(email_submissions)} submissions")
            factors["email_reuse"] = len(email_submissions)
        
        # Check file naming patterns
        similar_names = [
            s for s in database.get_submissions_by_fingerprint(fingerprint)
            if self._check_file_name_pattern(s.get("file_name", ""), file_name)
        ]
        if len(similar_names) > 1:
            score += 15
            signals.append(f"⚠ File naming pattern detected ({len(similar_names)} similar names)")
            factors["naming_pattern"] = len(similar_names)
        
        # Check submission timing patterns (e.g., always at night)
        all_by_fp = database.get_submissions_by_fingerprint(fingerprint)
        if len(all_by_fp) >= 2:
            hours = []
            for sub in all_by_fp:
                try:
                    dt = datetime.fromisoformat(sub.get("timestamp", ""))
                    hours.append(dt.hour)
                except Exception:
                    pass
            
            # Check for unusual timing (e.g., all between 2-4 AM)
            if hours and all(h >= 2 and h <= 4 for h in hours) and len(hours) >= 2:
                score += 20
                signals.append("• Suspicious timing pattern (automated submissions?)")
                factors["timing_pattern"] = True
        
        factors["velocity"] = fingerprint_velocity
        return score, signals, factors
    
    def _analyze_writing_style(self, metadata: Dict[str, Any]) -> tuple:
        """Layer 4: Writing Style Fingerprint"""
        score = 0
        signals = []
        factors = {}
        
        text_sample = metadata.get("text_sample", "")
        if not text_sample or len(text_sample) < 100:
            return 0, [], {}
        
        # Basic style analysis
        words = text_sample.split()
        sentences = text_sample.split('.')
        
        if len(sentences) > 0 and len(words) > 0:
            avg_sentence_length = len(words) / len(sentences)
            
            # Unusual sentence length patterns
            if avg_sentence_length < 5 or avg_sentence_length > 50:
                score += 5
                signals.append(f"• Unusual sentence structure (avg: {avg_sentence_length:.1f} words)")
                factors["unusual_style"] = True
        
        # Check for vocabulary richness
        unique_words = len({w.lower() for w in words if len(w) > 3})
        vocabulary_ratio = unique_words / len(words) if len(words) > 0 else 0
        
        if vocabulary_ratio < 0.3:  # Low vocabulary diversity
            score += 5
            signals.append("• Low vocabulary diversity (possible AI-generated?)")
            factors["low_vocabulary"] = vocabulary_ratio
        
        factors["writing_style_score"] = score
        return score, signals, factors
    
    def _analyze_content(self, metadata: Dict[str, Any], fingerprint: str) -> tuple:
        """Layer 5: Content Similarity"""
        score = 0
        signals = []
        factors = {}

        exact_score, exact_signals, exact_factors = self._score_exact_duplicates(metadata)
        score += exact_score
        signals.extend(exact_signals)
        factors.update(exact_factors)

        text_sample = metadata.get("text_sample", "")
        if text_sample:
            similarity_score, similarity_signals, similarity_factors = self._score_text_similarity(
                text_sample,
                fingerprint,
            )
            score += similarity_score
            signals.extend(similarity_signals)
            factors.update(similarity_factors)

            ai_score, ai_signals, ai_factors = self._score_ai_markers(text_sample)
            score += ai_score
            signals.extend(ai_signals)
            factors.update(ai_factors)

        factors["content_score"] = score
        return score, signals, factors

    def _score_exact_duplicates(self, metadata: Dict[str, Any]) -> tuple:
        """Score exact file duplicates across the entire corpus."""
        content_hash = metadata.get("content_hash", "")
        text_sample = metadata.get("text_sample", "")

        exact_duplicates = []
        if content_hash:
            exact_duplicates = database.get_submissions_by_content_hash(content_hash)

        if not exact_duplicates and text_sample:
            exact_duplicates = [
                sub
                for sub in database.get_all_submissions()
                if sub.get("metadata", {}).get("text_sample", "") == text_sample
            ]

        if not exact_duplicates:
            return 0, [], {}

        score = 35
        signals = [
            f"🔴 Exact file duplicate detected in {len(exact_duplicates)} prior submission(s)"
        ]
        factors = {"exact_file_duplicates": len(exact_duplicates)}
        return score, signals, factors

    def _score_text_similarity(self, text_sample: str, fingerprint: str) -> tuple:
        """Score similarity between the current text and prior submissions."""
        score = 0
        signals = []
        factors = {}

        current_words = set(text_sample.lower().split())
        if len(current_words) <= 10:
            return 0, [], {}

        for prev_sub in database.get_submissions_by_fingerprint(fingerprint):
            prev_text = prev_sub.get("metadata", {}).get("text_sample", "")
            if not prev_text or prev_text == text_sample:
                continue

            prev_words = set(prev_text.lower().split())
            if len(prev_words) <= 10:
                continue

            overlap = len(current_words & prev_words) / len(current_words | prev_words)
            if overlap > 0.7:
                score += 20
                signals.append("🔴 Content 70%+ similar to previous submission")
                factors["high_similarity"] = overlap
                break
            if overlap > 0.5:
                score += 10
                signals.append("⚠ Content 50%+ similar to previous submission")
                factors["medium_similarity"] = overlap
                break

        return score, signals, factors

    def _score_ai_markers(self, text_sample: str) -> tuple:
        """Score obvious AI-style marker usage."""
        ai_markers = ["however", "furthermore", "in conclusion", "in summary", "notably"]
        marker_count = sum(1 for marker in ai_markers if marker in text_sample.lower())

        if marker_count < 3:
            return 0, [], {}

        score = 5
        signals = ["• Possible AI-generated content (academic markers detected)"]
        factors = {"ai_markers": marker_count}
        return score, signals, factors
    
    def _check_file_name_pattern(self, name1: str, name2: str) -> bool:
        """Check if two filenames follow a pattern"""
        # Strip extensions
        n1 = name1.rsplit(".", 1)[0].lower()
        n2 = name2.rsplit(".", 1)[0].lower()
        
        # Check for version patterns like Paper_v1, Paper_v2
        import re
        pattern1 = re.sub(r'_v\d+|_\d+|v\d+', '', n1)
        pattern2 = re.sub(r'_v\d+|_\d+|v\d+', '', n2)
        
        if pattern1 == pattern2 and pattern1:
            return True
        
        # Check for common prefixes
        if len(n1) >= 5 and len(n2) >= 5 and n1[:5] == n2[:5]:
            return True
        
        return False
    
    def _get_risk_level(self, score: int) -> str:
        """Determine risk level based on score"""
        for level, (low, high) in self.risk_levels.items():
            if low <= score < high:
                return level
        return "critical"
    
    def _get_recommendation(self, score: int, signals: List[str]) -> str:
        """Generate recommendation based on score and signals"""
        if score < 30:
            return "✓ APPROVED: Submission appears legitimate"
        elif score < 60:
            return "⚠ REVIEW: Manual review recommended"
        elif score < 85:
            return "🔴 FLAG: High risk - likely spam/duplicate accounts"
        else:
            return "🚫 REJECT: Critical risk - suspected multi-account abuse"
