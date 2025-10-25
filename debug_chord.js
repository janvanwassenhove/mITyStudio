// Test the specific notes from the current issue: D4, A4, E4, G4
// This should NOT return C_major

const noteToSemitone = {
    'C': 0, 'B#': 0,              
    'C#': 1, 'Db': 1,             
    'D': 2, 
    'D#': 3, 'Eb': 3,             
    'E': 4, 'Fb': 4,              
    'F': 5, 'E#': 5,              
    'F#': 6, 'Gb': 6,             
    'G': 7, 
    'G#': 8, 'Ab': 8,             
    'A': 9, 
    'A#': 10, 'Bb': 10,          
    'B': 11, 'Cb': 11             
};

const notes = ['D4', 'A4', 'E4', 'G4'];
console.log('=== CHORD ANALYSIS TEST ===');
console.log('Input notes:', notes);

// Extract note names (remove octave numbers)
const noteNames = notes.map(note => note.replace(/\d+$/, ''));
const uniqueNotes = [...new Set(noteNames)].sort();
console.log('Note names:', noteNames, '→ Unique notes:', uniqueNotes);

// Convert to semitones
const noteSemitones = uniqueNotes
    .map(note => noteToSemitone[note])
    .filter(semitone => semitone !== undefined)
    .sort((a, b) => a - b);
console.log('Semitones:', noteSemitones);

// This is 4 notes: D(2), A(9), E(4), G(7) → sorted: [2, 4, 7, 9]
// Let's check what chords these could be:
console.log('\n=== CHORD PATTERN ANALYSIS ===');

const chordPatterns = {
    'major': [0, 4, 7],
    'minor': [0, 3, 7],
    'dom7': [0, 4, 7, 10],
    'maj7': [0, 4, 7, 11],
    'min7': [0, 3, 7, 10]
};

// Try each note as root
for (const rootSemitone of noteSemitones) {
    const rootNote = Object.keys(noteToSemitone).find(note => noteToSemitone[note] === rootSemitone);
    console.log(`\nTrying ${rootNote}(${rootSemitone}) as root:`);
    
    for (const [chordType, intervals] of Object.entries(chordPatterns)) {
        const expectedSemitones = intervals.map(interval => (rootSemitone + interval) % 12).sort((a, b) => a - b);
        const hasAllExpected = expectedSemitones.every(semitone => noteSemitones.includes(semitone));
        const hasOnlyExpected = noteSemitones.every(semitone => expectedSemitones.includes(semitone));
        
        if (hasAllExpected) {
            console.log(`  ${chordType}: Expected ${expectedSemitones}, we have ${noteSemitones} - ${hasAllExpected && hasOnlyExpected ? 'EXACT MATCH' : 'partial match'}`);
        }
    }
}

console.log('\n=== EXPECTED RESULT ===');
console.log('Since no exact chord match exists, should return: A_interval');
console.log('(A is first alphabetically in [A, D, E, G])');