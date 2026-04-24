import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { AssignmentView } from './pages/AssignmentView';
import { DataInput } from './pages/DataInput';
import { IssueBoard } from './pages/IssueBoard';
import { IssueExtraction } from './pages/IssueExtraction';
import { PriorityDashboard } from './pages/PriorityDashboard';
import { VolunteerMatching } from './pages/VolunteerMatching';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<PriorityDashboard />} />
          <Route path="/input" element={<DataInput />} />
          <Route path="/issues" element={<IssueBoard />} />
          <Route path="/extraction" element={<IssueExtraction />} />
          <Route path="/matching" element={<VolunteerMatching />} />
          <Route path="/assignments" element={<AssignmentView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
